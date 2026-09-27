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

# ── DB write-through imports ────────────────────────────────────────
try:
    from database.base import get_db_context, SessionLocal
    from database.models.langgraph_dlq import LanggraphDLQEntry
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

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
                "langgraph_dlq_recorded company_id=%s dlq_id=%s thread_id=%s error_type=%s graph_id=%s",
                company_id, dlq_id, thread_id, entry["error_type"], graph_id)
        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_record_failed company_id=%s dlq_id=%s error=%s",
                company_id, dlq_id, str(redis_exc)[:200])
            # Return the entry even if Redis write failed so the caller
            # can still log / emit it via an alternative channel.
            entry["_redis_persist_failed"] = True

        # ── DB write-through: persist to SQL ──────────────────────
        self._persist_failure_to_db(company_id, entry)

        return entry

    async def list_failures(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List DLQ entries for a company (newest first).

        Falls back to the DB if Redis returns no results.

        Args:
            company_id: Tenant identifier (BC-001).
            limit: Maximum number of entries to return (default 50).
            offset: Number of entries to skip (default 0).

        Returns:
            List of DLQ entry dicts, newest first.
        """
        entries: List[Dict[str, Any]] = []

        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)

            # Redis LRANGE is inclusive on both ends.
            # Index 0 = newest (leftmost), -1 = oldest (rightmost).
            start = offset
            stop = offset + limit - 1
            raw_entries = await redis.lrange(key, start, stop)

            for raw in raw_entries:
                try:
                    entry = json.loads(raw)
                    entries.append(entry)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "langgraph_dlq_malformed_entry company_id=%s raw_preview=%s",
                        company_id, str(raw)[:100])

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_list_failed company_id=%s error=%s",
                company_id, str(redis_exc)[:200])

        # ── DB fallback: query SQL if Redis returned nothing ──────
        if not entries:
            entries = self._list_failures_from_db(company_id, limit, offset)

        return entries

    async def get_failure(
        self,
        company_id: str,
        dlq_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single DLQ entry by its dlq_id.

        Scans the company's DLQ list for an entry with the matching
        ``dlq_id``. Falls back to DB if not found in Redis.

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

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_get_failed company_id=%s dlq_id=%s error=%s",
                company_id, dlq_id, str(redis_exc)[:200])

        # ── DB fallback: try SQL if not in Redis ────────────────────
        return self._get_failure_from_db(company_id, dlq_id)

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
        entry: Optional[Dict[str, Any]] = None

        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)

            # Find and remove the entry
            list_len = await redis.llen(key)
            raw_entries = await redis.lrange(key, 0, list_len - 1)

            for raw in raw_entries:
                try:
                    parsed = json.loads(raw)
                    if parsed.get("dlq_id") == dlq_id:
                        # Remove the exact JSON string from the list
                        removed = await redis.lrem(key, 1, raw)
                        if removed > 0:
                            entry = parsed
                            logger.info(
                                "langgraph_dlq_retry company_id=%s dlq_id=%s thread_id=%s graph_id=%s",
                                company_id, dlq_id, parsed.get("thread_id", ""), parsed.get("graph_id", ""))
                        else:
                            logger.warning(
                                "langgraph_dlq_retry_lrem_failed company_id=%s dlq_id=%s",
                                company_id, dlq_id)
                        break
                except (json.JSONDecodeError, TypeError):
                    continue

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_retry_error company_id=%s dlq_id=%s error=%s",
                company_id, dlq_id, str(redis_exc)[:200])

        # ── DB: mark as retried ─────────────────────────────────
        if entry is not None:
            self._update_db_entry_status(company_id, dlq_id, "retried")
        else:
            # Maybe it's only in DB (Redis was down when recorded)
            entry = self._get_failure_from_db(company_id, dlq_id)
            if entry is not None:
                self._update_db_entry_status(company_id, dlq_id, "retried")

        if entry is None:
            logger.info(
                "langgraph_dlq_retry_not_found company_id=%s dlq_id=%s",
                company_id, dlq_id)

        return entry

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
        found = False

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
                                "langgraph_dlq_cleared company_id=%s dlq_id=%s",
                                company_id, dlq_id)
                            found = True
                        break
                except (json.JSONDecodeError, TypeError):
                    continue

        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_clear_error company_id=%s dlq_id=%s error=%s",
                company_id, dlq_id, str(redis_exc)[:200])

        # ── DB: mark as cleared ─────────────────────────────────
        if found:
            self._update_db_entry_status(company_id, dlq_id, "cleared")
        else:
            # Maybe only in DB
            db_entry = self._get_failure_from_db(company_id, dlq_id)
            if db_entry is not None:
                self._update_db_entry_status(company_id, dlq_id, "cleared")
                found = True

        return found

    async def count_failures(
        self,
        company_id: str,
    ) -> int:
        """Count the number of DLQ entries for a company.

        Falls back to DB count if Redis is unavailable.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of entries in the DLQ, or 0 on error.
        """
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)
            count = await redis.llen(key)
            if count > 0:
                return count
        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_count_error company_id=%s error=%s",
                company_id, str(redis_exc)[:200])

        # ── DB fallback ───────────────────────────────────────────
        return self._count_failures_from_db(company_id)

    async def clear_all_failures(
        self,
        company_id: str,
    ) -> int:
        """Clear all DLQ entries for a company.

        Also marks all DB entries as cleared.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of entries that were in the DLQ before clearing.
        """
        count = 0
        try:
            redis = await get_redis()
            key = self._dlq_key(company_id)
            count = await redis.llen(key)
            if count > 0:
                await redis.delete(key)
            logger.info(
                "langgraph_dlq_cleared_all company_id=%s count=%s",
                company_id, count)
        except Exception as redis_exc:
            logger.error(
                "langgraph_dlq_clear_all_error company_id=%s error=%s",
                company_id, str(redis_exc)[:200])

        # ── DB: mark all pending entries as cleared ───────────────
        self._clear_all_db_entries(company_id)

        return count

    # ── DB Persistence Helpers ──────────────────────────────────────

    def _persist_failure_to_db(
        self,
        company_id: str,
        entry: Dict[str, Any],
    ) -> None:
        """Write a DLQ entry to the LanggraphDLQEntry SQL table.

        Args:
            company_id: Tenant identifier (BC-001).
            entry: The DLQ entry dict (from record_failure).
        """
        if not _DB_AVAILABLE:
            return

        try:
            with get_db_context() as db:
                row = LanggraphDLQEntry(
                    company_id=company_id,
                    dlq_id=entry.get("dlq_id", str(uuid.uuid4())),
                    graph_id=entry.get("graph_id"),
                    thread_id=entry.get("thread_id", ""),
                    error_message=entry.get("error_message", "")[:2000],
                    error_type=entry.get("error_type"),
                    state_snapshot=json.dumps(
                        entry.get("state_snapshot", {}), default=str
                    ),
                    status="pending",
                )
                db.add(row)
        except Exception as exc:
            logger.warning(
                "langgraph_dlq_db_persist_failed",
                extra={
                    "company_id": company_id,
                    "dlq_id": entry.get("dlq_id"),
                    "error": str(exc)[:200],
                },
            )

    def _list_failures_from_db(
        self,
        company_id: str,
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        """Query DLQ entries from the SQL table for a company.

        Args:
            company_id: Tenant identifier (BC-001).
            limit: Max entries to return.
            offset: Number of entries to skip.

        Returns:
            List of DLQ entry dicts.
        """
        if not _DB_AVAILABLE:
            return []

        try:
            with get_db_context() as db:
                rows = (
                    db.query(LanggraphDLQEntry)
                    .filter_by(company_id=company_id, status="pending")
                    .order_by(LanggraphDLQEntry.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "dlq_id": row.dlq_id,
                        "graph_id": row.graph_id or "",
                        "thread_id": row.thread_id,
                        "error_message": row.error_message or "",
                        "error_type": row.error_type or "",
                        "state_snapshot": (
                            json.loads(row.state_snapshot)
                            if row.state_snapshot
                            else {}
                        ),
                        "timestamp": row.created_at.isoformat() if row.created_at else "",
                        "status": row.status,
                    }
                    for row in rows
                ]
        except Exception as exc:
            logger.warning(
                "langgraph_dlq_db_list_failed",
                extra={"company_id": company_id, "error": str(exc)[:200]},
            )
            return []

    def _get_failure_from_db(
        self,
        company_id: str,
        dlq_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single DLQ entry from the SQL table.

        Args:
            company_id: Tenant identifier (BC-001).
            dlq_id: The unique DLQ entry identifier.

        Returns:
            DLQ entry dict, or None if not found.
        """
        if not _DB_AVAILABLE:
            return None

        try:
            with get_db_context() as db:
                row = (
                    db.query(LanggraphDLQEntry)
                    .filter_by(company_id=company_id, dlq_id=dlq_id)
                    .first()
                )
                if row is None:
                    return None
                return {
                    "dlq_id": row.dlq_id,
                    "graph_id": row.graph_id or "",
                    "thread_id": row.thread_id,
                    "error_message": row.error_message or "",
                    "error_type": row.error_type or "",
                    "state_snapshot": (
                        json.loads(row.state_snapshot)
                        if row.state_snapshot
                        else {}
                    ),
                    "timestamp": row.created_at.isoformat() if row.created_at else "",
                    "status": row.status,
                }
        except Exception as exc:
            logger.warning(
                "langgraph_dlq_db_get_failed",
                extra={
                    "company_id": company_id,
                    "dlq_id": dlq_id,
                    "error": str(exc)[:200],
                },
            )
            return None

    def _update_db_entry_status(
        self,
        company_id: str,
        dlq_id: str,
        status: str,
    ) -> None:
        """Update the status of a DLQ entry in the SQL table.

        Args:
            company_id: Tenant identifier (BC-001).
            dlq_id: The unique DLQ entry identifier.
            status: New status (retried, cleared).
        """
        if not _DB_AVAILABLE:
            return

        try:
            with get_db_context() as db:
                row = (
                    db.query(LanggraphDLQEntry)
                    .filter_by(company_id=company_id, dlq_id=dlq_id)
                    .first()
                )
                if row is not None:
                    row.status = status
                    row.updated_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning(
                "langgraph_dlq_db_status_update_failed",
                extra={
                    "company_id": company_id,
                    "dlq_id": dlq_id,
                    "status": status,
                    "error": str(exc)[:200],
                },
            )

    def _count_failures_from_db(self, company_id: str) -> int:
        """Count pending DLQ entries from the SQL table.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Count of pending entries, or 0 on error.
        """
        if not _DB_AVAILABLE:
            return 0

        try:
            with get_db_context() as db:
                return (
                    db.query(LanggraphDLQEntry)
                    .filter_by(company_id=company_id, status="pending")
                    .count()
                )
        except Exception as exc:
            logger.warning(
                "langgraph_dlq_db_count_failed",
                extra={"company_id": company_id, "error": str(exc)[:200]},
            )
            return 0

    def _clear_all_db_entries(self, company_id: str) -> int:
        """Mark all pending DLQ entries as cleared in the SQL table.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of entries marked as cleared.
        """
        if not _DB_AVAILABLE:
            return 0

        try:
            with get_db_context() as db:
                rows = (
                    db.query(LanggraphDLQEntry)
                    .filter_by(company_id=company_id, status="pending")
                    .all()
                )
                now = datetime.now(timezone.utc)
                for row in rows:
                    row.status = "cleared"
                    row.updated_at = now
                return len(rows)
        except Exception as exc:
            logger.warning(
                "langgraph_dlq_db_clear_all_failed",
                extra={"company_id": company_id, "error": str(exc)[:200]},
            )
            return 0
