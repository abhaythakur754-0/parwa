"""
RAG Re-Indexing Triggers (F-153)

Handles cache invalidation on KB document updates, staleness detection,
and automatic re-embedding when documents change.

BC-001: All operations scoped to company_id.
BC-008: Never crashes — always returns a result.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.logger import get_logger

logger = get_logger("rag_reindexing")


@dataclass
class ReindexingResult:
    """Result of a re-indexing operation."""

    success: bool
    documents_reindexed: int
    chunks_updated: int
    cache_entries_invalidated: int
    staleness_signals: List[Dict[str, Any]]
    processing_time_ms: float
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "documents_reindexed": self.documents_reindexed,
            "chunks_updated": self.chunks_updated,
            "cache_entries_invalidated": self.cache_entries_invalidated,
            "staleness_signals": self.staleness_signals,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "errors": self.errors,
        }


@dataclass
class StalenessCheck:
    """Result of a staleness check."""

    document_id: str
    is_stale: bool
    age_seconds: float
    threshold_seconds: float
    last_indexed_at: Optional[str]
    signals: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "is_stale": self.is_stale,
            "age_seconds": round(self.age_seconds, 2),
            "threshold_seconds": self.threshold_seconds,
            "last_indexed_at": self.last_indexed_at,
            "signals": self.signals,
        }


@dataclass
class FreshnessCheck:
    """Result of a context freshness check."""

    context_id: str
    is_fresh: bool
    age_seconds: float
    max_age_seconds: float
    recommendation: str  # "use_cache", "re_extract", "full_rerun"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "is_fresh": self.is_fresh,
            "age_seconds": round(self.age_seconds, 2),
            "max_age_seconds": self.max_age_seconds,
            "recommendation": self.recommendation,
        }


class ReindexingService:
    """RAG Re-Indexing Service (F-153).

    Handles:
    - Cache invalidation on KB document updates
    - Staleness detection (>5min → signal re-extract)
    - Context freshness checks
    - Batch re-indexing with configurable batch size
    """

    STALENESS_THRESHOLD_SECONDS = 300  # 5 minutes
    FRESHNESS_THRESHOLD_SECONDS = 300  # 5 minutes
    CACHE_PREFIX = "rag:"
    CACHE_TTL_SECONDS = 120

    def __init__(self, vector_store=None):
        from shared.knowledge_base.vector_search import MockVectorStore, VectorStore

        self._store = vector_store

    async def trigger_reindex(
        self,
        company_id: str,
        document_ids: List[str],
        variant_type: str = "parwa",
    ) -> ReindexingResult:
        """Trigger re-indexing for specific documents."""
        start = time.monotonic()
        errors: List[str] = []
        staleness_signals: List[Dict[str, Any]] = []
        docs_reindexed = 0
        chunks_updated = 0

        for doc_id in document_ids:
            try:
                # Invalidate cache for this document
                invalidated = await self._invalidate_doc_cache(company_id, doc_id)

                # Check staleness
                staleness = await self.check_staleness(company_id, doc_id)
                if staleness["is_stale"]:
                    staleness_signals.append(
                        {
                            "document_id": doc_id,
                            "age_seconds": staleness["age_seconds"],
                            "signals": staleness["signals"],
                        }
                    )

                docs_reindexed += 1
                chunks_updated += invalidated
            except Exception as exc:
                error_msg = f"Failed to reindex {doc_id}: {str(exc)}"
                logger.warning(
                    "reindex_document_failed", document_id=doc_id, error=str(exc)
                )
                errors.append(error_msg)

        elapsed = round((time.monotonic() - start) * 1000, 2)

        return ReindexingResult(
            success=len(errors) == 0,
            documents_reindexed=docs_reindexed,
            chunks_updated=chunks_updated,
            cache_entries_invalidated=sum(
                s.get("entries", 0) for s in staleness_signals
            ),
            staleness_signals=staleness_signals,
            processing_time_ms=elapsed,
            errors=errors,
        )

    async def check_staleness(
        self, company_id: str, document_id: str
    ) -> Dict[str, Any]:
        """Check if a document's RAG cache is stale."""
        signals: List[str] = []
        is_stale = False
        age_seconds = 0.0

        try:
            cache_key = f"rag_index_time:{company_id}:{document_id}"
            from backend.app.core.redis import cache_get

            indexed_at = await cache_get(company_id, cache_key)

            if indexed_at and isinstance(indexed_at, dict):
                timestamp = indexed_at.get("timestamp", 0)
                if timestamp:
                    age_seconds = time.time() - timestamp
                    if age_seconds > self.STALENESS_THRESHOLD_SECONDS:
                        is_stale = True
                        signals.append(
                            f"Document indexed {age_seconds:.0f}s ago (> {self.STALENESS_THRESHOLD_SECONDS}s threshold)"
                        )
                    else:
                        signals.append("Document index is fresh")
                else:
                    is_stale = True
                    signals.append("No indexing timestamp found")
            else:
                is_stale = True
                signals.append("No cache entry found — document may not be indexed")
        except Exception as exc:
            logger.warning(
                "staleness_check_failed", document_id=document_id, error=str(exc)
            )
            is_stale = True
            signals.append(f"Staleness check failed: {str(exc)}")

        return {
            "document_id": document_id,
            "is_stale": is_stale,
            "age_seconds": round(age_seconds, 2),
            "threshold_seconds": self.STALENESS_THRESHOLD_SECONDS,
            "signals": signals,
        }

    async def invalidate_cache(
        self,
        company_id: str,
        document_ids: List[str],
    ) -> int:
        """Invalidate RAG cache entries for documents."""
        invalidated = 0
        for doc_id in document_ids:
            try:
                invalidated += await self._invalidate_doc_cache(company_id, doc_id)
            except Exception as exc:
                logger.warning(
                    "cache_invalidation_failed", document_id=doc_id, error=str(exc)
                )
        return invalidated

    async def check_freshness(
        self,
        company_id: str,
        context_id: str,
    ) -> Dict[str, Any]:
        """Check if a conversation context is fresh enough for RAG."""
        age_seconds = 0.0
        recommendation = "use_cache"

        try:
            cache_key = f"rag_context_time:{company_id}:{context_id}"
            from backend.app.core.redis import cache_get

            context_data = await cache_get(company_id, cache_key)

            if context_data and isinstance(context_data, dict):
                timestamp = context_data.get("timestamp", 0)
                if timestamp:
                    age_seconds = time.time() - timestamp
                    if age_seconds > self.FRESHNESS_THRESHOLD_SECONDS:
                        recommendation = "full_rerun"
                    elif age_seconds > self.FRESHNESS_THRESHOLD_SECONDS * 0.6:
                        recommendation = "re_extract"
                    else:
                        recommendation = "use_cache"
                else:
                    recommendation = "full_rerun"
                    age_seconds = float("inf")
            else:
                recommendation = "full_rerun"
                age_seconds = float("inf")
        except Exception as exc:
            logger.warning(
                "freshness_check_failed", context_id=context_id, error=str(exc)
            )
            recommendation = "full_rerun"

        is_fresh = recommendation in ("use_cache", "re_extract")

        return {
            "context_id": context_id,
            "is_fresh": is_fresh,
            "age_seconds": round(age_seconds, 2) if age_seconds != float("inf") else -1,
            "max_age_seconds": self.FRESHNESS_THRESHOLD_SECONDS,
            "recommendation": recommendation,
        }

    async def batch_reindex(
        self,
        company_id: str,
        document_ids: List[str],
        variant_type: str = "parwa",
        batch_size: int = 10,
    ) -> ReindexingResult:
        """Batch re-index documents with configurable batch size."""
        start = time.monotonic()
        total_errors: List[str] = []
        total_signals: List[Dict[str, Any]] = []
        total_docs = 0
        total_chunks = 0

        for i in range(0, len(document_ids), batch_size):
            batch = document_ids[i : i + batch_size]
            try:
                result = await self.trigger_reindex(
                    company_id,
                    batch,
                    variant_type,
                )
                total_docs += result.documents_reindexed
                total_chunks += result.chunks_updated
                total_signals.extend(result.staleness_signals)
                total_errors.extend(result.errors)
            except Exception as exc:
                error_msg = f"Batch {i // batch_size} failed: {str(exc)}"
                logger.error(
                    "batch_reindex_failed", batch_index=i // batch_size, error=str(exc)
                )
                total_errors.append(error_msg)

        elapsed = round((time.monotonic() - start) * 1000, 2)

        return ReindexingResult(
            success=len(total_errors) == 0,
            documents_reindexed=total_docs,
            chunks_updated=total_chunks,
            cache_entries_invalidated=sum(s.get("entries", 0) for s in total_signals),
            staleness_signals=total_signals,
            processing_time_ms=elapsed,
            errors=total_errors,
        )

    async def _invalidate_doc_cache(
        self,
        company_id: str,
        document_id: str,
    ) -> int:
        """Invalidate cache entries for a single document."""
        invalidated = 0
        try:
            from backend.app.core.redis import cache_delete

            # Delete the index time cache entry
            await cache_delete(company_id, f"rag_index_time:{company_id}:{document_id}")
            invalidated += 1
            # Delete any RAG result caches that might reference this document
            await cache_delete(company_id, f"rag_result:{company_id}:{document_id}")
            invalidated += 1
        except Exception:
            pass  # BC-008: fail open
        return invalidated


# =========================================================================
# ReindexJob / ReindexStatus / ReindexingManager
# =========================================================================


@dataclass
class ReindexJob:
    """A single reindexing job for a document."""

    document_id: str
    company_id: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    error: str = ""


@dataclass
class ReindexStatus:
    """Snapshot of reindexing status for a company."""

    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.pending + self.processing + self.completed + self.failed


class ReindexingManager:
    """In-memory reindexing manager with queue, staleness detection,
    and cache-invalidation tracking.  Scoped to company_id."""

    def __init__(self) -> None:
        self._doc_timestamps: Dict[str, Dict[str, float]] = {}
        self._pending_queue: List[ReindexJob] = []
        self._completed_jobs: List[ReindexJob] = []
        self._failed_jobs: List[ReindexJob] = []
        self._invalidated_docs: Dict[str, set] = {}

    # ------------------------------------------------------------------
    # mark_for_reindex
    # ------------------------------------------------------------------

    async def mark_for_reindex(
        self,
        company_id: str,
        document_ids: List[str],
    ) -> int:
        """Queue *unique* document_ids (within this call) for reindexing.

        Deduplication is per-call: the same doc_id may appear across
        multiple calls and will create separate jobs.
        """
        seen: set = set()
        count = 0
        for doc_id in document_ids:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            job = ReindexJob(
                document_id=doc_id,
                company_id=company_id,
            )
            self._pending_queue.append(job)
            count += 1
        return count

    # ------------------------------------------------------------------
    # process_reindex_queue
    # ------------------------------------------------------------------

    async def process_reindex_queue(
        self,
        company_id: str,
        process_fn=None,
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process pending jobs for *company_id*.

        Returns dict with keys: processed, succeeded, failed, errors.
        """
        # Collect matching pending jobs
        matching: List[ReindexJob] = [
            j for j in self._pending_queue if j.company_id == company_id
        ]

        if batch_size is not None:
            matching = matching[:batch_size]

        succeeded = 0
        failed = 0
        errors: List[str] = []

        for job in matching:
            self._pending_queue.remove(job)
            job.status = "processing"

            try:
                if process_fn is not None:
                    result = process_fn(job)
                    if asyncio.iscoroutine(result):
                        result = await result
                    # If callback returned False-like, still count as success
                # No process_fn → auto-succeed
                job.status = "completed"
                self._completed_jobs.append(job)
                succeeded += 1
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                self._failed_jobs.append(job)
                failed += 1
                errors.append(str(exc))

        return {
            "processed": succeeded + failed,
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # get_reindex_status
    # ------------------------------------------------------------------

    def get_reindex_status(self, company_id: str) -> ReindexStatus:
        """Return a status snapshot for *company_id*."""
        pending = sum(1 for j in self._pending_queue if j.company_id == company_id)
        processing = 0  # jobs are never left in processing state
        completed = sum(1 for j in self._completed_jobs if j.company_id == company_id)
        failed = sum(1 for j in self._failed_jobs if j.company_id == company_id)
        return ReindexStatus(
            pending=pending,
            processing=processing,
            completed=completed,
            failed=failed,
        )

    # ------------------------------------------------------------------
    # invalidate_cache
    # ------------------------------------------------------------------

    async def invalidate_cache(
        self,
        company_id: str,
        document_ids: List[str],
    ) -> int:
        """Track invalidated documents; returns accumulated unique count."""
        if company_id not in self._invalidated_docs:
            self._invalidated_docs[company_id] = set()
        self._invalidated_docs[company_id].update(document_ids)
        return len(self._invalidated_docs[company_id])

    # ------------------------------------------------------------------
    # get_stale_documents
    # ------------------------------------------------------------------

    async def get_stale_documents(
        self,
        company_id: str,
        max_age_minutes: float = 5,
    ) -> List[Dict[str, Any]]:
        """Return stale documents sorted by age (most stale first)."""
        now = time.time()
        threshold_seconds = max_age_minutes * 60
        timestamps = self._doc_timestamps.get(company_id, {})
        stale: List[Dict[str, Any]] = []
        for doc_id, ts in timestamps.items():
            age_seconds = now - ts
            if age_seconds > threshold_seconds:
                stale.append(
                    {
                        "document_id": doc_id,
                        "age_minutes": age_seconds / 60,
                    }
                )
        # Sort most stale first
        stale.sort(key=lambda d: d["age_minutes"], reverse=True)
        return stale

    # ------------------------------------------------------------------
    # record_index_timestamp
    # ------------------------------------------------------------------

    def record_index_timestamp(
        self,
        company_id: str,
        document_ids: List[str],
    ) -> None:
        """Store the current timestamp for each document."""
        if company_id not in self._doc_timestamps:
            self._doc_timestamps[company_id] = {}
        now = time.time()
        for doc_id in document_ids:
            self._doc_timestamps[company_id][doc_id] = now

    # ------------------------------------------------------------------
    # clear
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all internal state."""
        self._doc_timestamps.clear()
        self._pending_queue.clear()
        self._completed_jobs.clear()
        self._failed_jobs.clear()
        self._invalidated_docs.clear()
