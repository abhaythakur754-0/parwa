"""
LangGraph Dead Letter Queue (DLQ) Service

Records failed LangGraph graph executions for later inspection,
manual retry, or analysis. Uses Redis LISTs per company to store
failure entries.

Redis Key Pattern:
    parwa:{company_id}:langgraph:dlq  (Redis LIST)

Each DLQ entry is a JSON object with:
    - dlq_id:       Unique identifier (UUID)
    - graph_id:     LangGraph graph/run identifier
    - thread_id:    Conversation thread identifier
    - error_message:Human-readable error description
    - error_type:   Exception class name (e.g. RateLimitError)
    - state_snapshot: JSON snapshot of the graph state at failure
    - timestamp:    ISO-8601 UTC timestamp

BC-001: All keys are tenant-scoped (parwa:{company_id}:*).
BC-008: Never crash — all methods handle Redis failures gracefully.
BC-012: All timestamps UTC.

Usage:
    from app.services.langgraph_dlq_service import LanggraphDLQService

    dlq = LanggraphDLQService()

    # Record a failure
    await dlq.record_failure(
        company_id="acme",
        thread_id="thread_123",
        error=exc,
        state_snapshot=state_dict,
        graph_id="run_abc",
    )

    # List failures
    entries = await dlq.list_failures("acme", limit=20)

    # Get a single failure
    entry = await dlq.get_failure("acme", "dlq_uuid_here")

    # Retry — removes from DLQ and returns for re-execution
    entry = await dlq.retry_failure("acme", "dlq_uuid_here")

    # Clear a failure
    await dlq.clear_failure("acme", "dlq_uuid_here")
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.redis import get_redis, make_key
from app.logger import get_logger

logger = get_logger("langgraph_dlq_service")


class LanggraphDLQService:
    """Dead Letter Queue for failed LangGraph executions.

    Stores failed graph executions in Redis (LIST per company) so
    operators can inspect, retry, or purge them. All keys are
    tenant-scoped per BC-001.

    Redis key format: ``parwa:{company_id}:langgraph:dlq``
    Each element in the list is a JSON-serialized DLQ entry.
    New entries are pushed to the left (LPUSH) so index 0 is newest.
    """

    # ── Redis list operations ─────────────────────────────────────

    @staticmethod
    def _dlq_key(company_id: str) -> str:
        """Build the Redis key for a company's DLQ list.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Redis key string: ``parwa:{company_id}:langgraph:dlq``
        """
        return make_key(company_id, "langgraph", "dlq")

    # ── Public API ────────────────────────────────────────────────

    async def record_failure(
        self,
        company_id: str,
        thread_id: str,
        error: Exception,
        state_snapshot: Optional[Dict[str, Any]] = None,
        graph_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a failed LangGraph execution in the DLQ.

        Adds the failure entry to the left of the company's DLQ list
        so the most recent failure is always at index 0.

        Args:
            company_id: Tenant identifier (BC-001).
            thread_id: Conversation thread identifier.
            error: The exception that caused the failure.
            state_snapshot: JSON-serializable snapshot of graph state.
            graph_id: Optional graph/run identifier.

        Returns:
            The created DLQ entry dict (includes ``dlq_id``).
        """
        dlq_id = str(uuid.uuid4())
        entry: Dict[str, Any] = {
            "dlq_id": dlq_id,
            "graph_id": graph_id or "",
            "thread_id": thread_id,
            "error_message": str(error)[:2000],
            "error_type": type(error).__name__,
            "state_snapshot": state_snapshot or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)
            serialized = json.dumps(entry, default=str)
            await redis.lpush(key, serialized)

            logger.info(
                "langgraph_dlq_recorded",
                company_id=company_id,
                dlq_id=dlq_id,
                thread_id=thread_id,
                error_type=entry["error_type"],
                graph_id=graph_id,
            )
        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_record_failed",
                company_id=company_id,
                dlq_id=dlq_id,
                error=str(redis_exc)[:200],
            )
            # Return the entry even if Redis write failed so the caller
            # can still log / emit it via an alternative channel.
            entry["_redis_persist_failed"] = True

        return entry

    async def list_failures(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List DLQ entries for a company (newest first).

        Args:
            company_id: Tenant identifier (BC-001).
            limit: Maximum number of entries to return (default 50).
            offset: Number of entries to skip (default 0).

        Returns:
            List of DLQ entry dicts, newest first.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)

            # Redis LRANGE is inclusive on both ends.
            # Index 0 = newest (leftmost), -1 = oldest (rightmost).
            start = offset
            stop = offset + limit - 1
            raw_entries = await redis.lrange(key, start, stop)

            entries: List[Dict[str, Any]] = []
            for raw in raw_entries:
                try:
                    entry = json.loads(raw)
                    entries.append(entry)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "langgraph_dlq_malformed_entry",
                        company_id=company_id,
                        raw_preview=str(raw)[:100],
                    )

            return entries

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_list_failed",
                company_id=company_id,
                error=str(redis_exc)[:200],
            )
            return []

    async def get_failure(
        self,
        company_id: str,
        dlq_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single DLQ entry by its dlq_id.

        Scans the company's DLQ list for an entry with the matching
        ``dlq_id``. Returns ``None`` if not found.

        Args:
            company_id: Tenant identifier (BC-001).
            dlq_id: The unique DLQ entry identifier.

        Returns:
            DLQ entry dict, or ``None`` if not found.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)

            # Scan the list for the matching dlq_id.
            # DLQ lists are typically small (<1000 entries), so a full
            # scan is acceptable. For very large DLQs, consider a
            # secondary Redis HASH index.
            list_len = await redis.llen(key)
            raw_entries = await redis.lrange(key, 0, list_len - 1)

            for raw in raw_entries:
                try:
                    entry = json.loads(raw)
                    if entry.get("dlq_id") == dlq_id:
                        return entry
                except (json.JSONDecodeError, TypeError):
                    continue

            return None

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_get_failed",
                company_id=company_id,
                dlq_id=dlq_id,
                error=str(redis_exc)[:200],
            )
            return None

    async def retry_failure(
        self,
        company_id: str,
        dlq_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Remove a failure from the DLQ and return it for retry.

        Finds the DLQ entry with the given ``dlq_id``, removes it
        from the list, and returns it so the caller can re-inject
        the state into a new graph execution.

        Args:
            company_id: Tenant identifier (BC-001).
            dlq_id: The unique DLQ entry identifier.

        Returns:
            DLQ entry dict ready for retry, or ``None`` if not found.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)

            # Find and remove the entry
            list_len = await redis.llen(key)
            raw_entries = await redis.lrange(key, 0, list_len - 1)

            for raw in raw_entries:
                try:
                    entry = json.loads(raw)
                    if entry.get("dlq_id") == dlq_id:
                        # Remove the exact JSON string from the list
                        removed = await redis.lrem(key, 1, raw)
                        if removed > 0:
                            logger.info(
                                "langgraph_dlq_retry",
                                company_id=company_id,
                                dlq_id=dlq_id,
                                thread_id=entry.get("thread_id", ""),
                                graph_id=entry.get("graph_id", ""),
                            )
                            return entry
                        else:
                            logger.warning(
                                "langgraph_dlq_retry_lrem_failed",
                                company_id=company_id,
                                dlq_id=dlq_id,
                            )
                            return None
                except (json.JSONDecodeError, TypeError):
                    continue

            logger.info(
                "langgraph_dlq_retry_not_found",
                company_id=company_id,
                dlq_id=dlq_id,
            )
            return None

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_retry_error",
                company_id=company_id,
                dlq_id=dlq_id,
                error=str(redis_exc)[:200],
            )
            return None

    async def clear_failure(
        self,
        company_id: str,
        dlq_id: str,
    ) -> bool:
        """Remove a failure from the DLQ permanently.

        Unlike ``retry_failure``, this does not return the entry —
        it is simply purged.

        Args:
            company_id: Tenant identifier (BC-001).
            dlq_id: The unique DLQ entry identifier.

        Returns:
            ``True`` if the entry was found and removed, ``False`` otherwise.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)

            list_len = await redis.llen(key)
            raw_entries = await redis.lrange(key, 0, list_len - 1)

            for raw in raw_entries:
                try:
                    entry = json.loads(raw)
                    if entry.get("dlq_id") == dlq_id:
                        removed = await redis.lrem(key, 1, raw)
                        if removed > 0:
                            logger.info(
                                "langgraph_dlq_cleared",
                                company_id=company_id,
                                dlq_id=dlq_id,
                            )
                            return True
                        return False
                except (json.JSONDecodeError, TypeError):
                    continue

            return False

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_clear_error",
                company_id=company_id,
                dlq_id=dlq_id,
                error=str(redis_exc)[:200],
            )
            return False

    async def count_failures(
        self,
        company_id: str,
    ) -> int:
        """Count the number of DLQ entries for a company.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of entries in the DLQ, or 0 on error.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)
            return await redis.llen(key)
        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_count_error",
                company_id=company_id,
                error=str(redis_exc)[:200],
            )
            return 0

    async def clear_all_failures(
        self,
        company_id: str,
    ) -> int:
        """Clear all DLQ entries for a company.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of entries that were in the DLQ before clearing.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)
            count = await redis.llen(key)
            if count > 0:
                await redis.delete(key)
            logger.info(
                "langgraph_dlq_cleared_all",
                company_id=company_id,
                count=count,
            )
            return count
        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_clear_all_error",
                company_id=company_id,
                error=str(redis_exc)[:200],
            )
            return 0
