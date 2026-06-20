"""
PARWA LangGraph Dead Letter Queue (DB-backed)

Persists failed graph executions to PostgreSQL for durability and later retry,
in addition to the existing Redis DLQ (7-day TTL).

LG-02: Redis-only DLQ is ephemeral — if Redis restarts, all DLQ entries are
lost.  This module adds a PostgreSQL-backed DLQ so that failed executions
survive infrastructure restarts and can be queried/retried by operators.

Dual-write strategy:
  1. Redis (7-day TTL) — fast lookups, real-time dashboards
  2. PostgreSQL — durable, queryable, supports retry/resolution lifecycle

All DB writes are fire-and-forget (synchronous inside the async helper)
so that a DB outage never blocks the fallback response path (BC-008).
"""

from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.logger import get_logger

logger = get_logger("langgraph_dlq")


# ══════════════════════════════════════════════════════════════════
# DB MODEL
# ══════════════════════════════════════════════════════════════════

from database.base import Base


class GraphExecutionDLQ(Base):
    """Persistent record of a failed graph execution.

    Survives Redis restarts.  Supports retry/resolution lifecycle so
    operators can replay failed conversations without manual data entry.
    """

    __tablename__ = "graph_execution_dlq"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(36), nullable=True)
    error = Column(Text, nullable=False)
    error_type = Column(String(100), nullable=True)  # timeout, llm_error, node_crash, etc.
    state_snapshot = Column(Text, nullable=True)  # JSON of key state fields
    variant_tier = Column(String(20), nullable=True)
    channel = Column(String(20), nullable=True)
    intent = Column(String(50), nullable=True)
    retried = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    retry_succeeded = Column(Boolean, nullable=True)
    last_retry_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


# ══════════════════════════════════════════════════════════════════
# DLQ SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

# Key state fields to extract for the lightweight snapshot
_SNAPSHOT_KEYS = (
    "message", "channel", "customer_id", "tenant_id",
    "variant_tier", "intent", "target_agent",
    "agent_response", "agent_confidence",
)


def _classify_error(error: str) -> str:
    """Return a short error_type tag from the error message text."""
    error_lower = error.lower()
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "rate" in error_lower and "limit" in error_lower:
        return "rate_limit"
    if "429" in error_lower:
        return "rate_limit"
    if "quota" in error_lower:
        return "quota_exceeded"
    if "auth" in error_lower or "api key" in error_lower or "401" in error_lower:
        return "llm_auth_error"
    if "connection" in error_lower or "refused" in error_lower:
        return "connection_error"
    if "crash" in error_lower or "segfault" in error_lower:
        return "node_crash"
    return "unknown"


def persist_to_dlq(
    company_id: str,
    conversation_id: str,
    error: str,
    state_snapshot: dict,
    *,
    session_id: str | None = None,
    error_type: str | None = None,
    variant_tier: str | None = None,
    channel: str | None = None,
    intent: str | None = None,
) -> str | None:
    """Write a failed execution to both Redis (7-day TTL) AND PostgreSQL.

    This is a **synchronous, fire-and-forget** function designed to be called
    from inside ``_persist_to_dlq`` in graph.py.  It must never raise — the
    caller wraps it in a try/except safety net.

    Returns the DB entry id on success, or ``None`` on failure.
    """
    entry_id = str(uuid4())

    # ── 1. Extract lightweight snapshot ──────────────────────────
    snapshot = {
        k: v for k, v in state_snapshot.items()
        if k in _SNAPSHOT_KEYS
    }
    snapshot_json = _json.dumps(snapshot, default=str)

    # ── 2. Classify error if caller didn't provide a type ───────
    if not error_type:
        error_type = _classify_error(error)

    # ── 3. Enrich variant_tier / channel / intent from snapshot ─
    if not variant_tier:
        variant_tier = snapshot.get("variant_tier")
    if not channel:
        channel = snapshot.get("channel")
    if not intent:
        intent = snapshot.get("intent")

    # ── 4. Write to Redis (7-day TTL, same format as before) ────
    _persist_to_redis(
        company_id=company_id,
        conversation_id=conversation_id,
        error=error,
        snapshot=snapshot,
        entry_id=entry_id,
    )

    # ── 5. Write to PostgreSQL ──────────────────────────────────
    return _persist_to_db(
        entry_id=entry_id,
        company_id=company_id,
        conversation_id=conversation_id,
        session_id=session_id,
        error=error,
        error_type=error_type,
        snapshot_json=snapshot_json,
        variant_tier=variant_tier,
        channel=channel,
        intent=intent,
    )


# ── Redis write (internal) ──────────────────────────────────────

def _persist_to_redis(
    *,
    company_id: str,
    conversation_id: str,
    error: str,
    snapshot: dict,
    entry_id: str,
) -> None:
    """Write DLQ entry to Redis with 7-day TTL (best-effort)."""
    try:
        from app.core.redis_client import get_redis_client

        redis = get_redis_client()
        dlq_entry = {
            "id": entry_id,
            "company_id": company_id,
            "conversation_id": conversation_id,
            "error": error,
            "state_snapshot": snapshot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retried": False,
        }
        key = f"parwa:langgraph:dlq:{company_id}:{conversation_id or 'no-conv'}"
        redis.setex(key, 7 * 24 * 3600, _json.dumps(dlq_entry))

        logger.info(
            "langgraph_dlq_redis_persisted",
            company_id=company_id,
            conversation_id=conversation_id,
            entry_id=entry_id,
        )
    except Exception as exc:
        logger.warning(
            "langgraph_dlq_redis_persist_failed",
            company_id=company_id,
            error=str(exc)[:200],
        )


# ── PostgreSQL write (internal) ─────────────────────────────────

def _persist_to_db(
    *,
    entry_id: str,
    company_id: str,
    conversation_id: str,
    session_id: str | None,
    error: str,
    error_type: str,
    snapshot_json: str,
    variant_tier: str | None,
    channel: str | None,
    intent: str | None,
) -> str | None:
    """Write DLQ entry to PostgreSQL (fire-and-forget).

    Returns entry_id on success, None on failure.
    """
    try:
        from database.base import SessionLocal

        with SessionLocal() as db:
            entry = GraphExecutionDLQ(
                id=entry_id,
                company_id=company_id,
                conversation_id=conversation_id or None,
                session_id=session_id,
                error=error[:2000],  # cap to prevent oversized rows
                error_type=error_type,
                state_snapshot=snapshot_json,
                variant_tier=variant_tier,
                channel=channel,
                intent=intent,
            )
            db.add(entry)
            db.commit()

        logger.info(
            "langgraph_dlq_db_persisted",
            company_id=company_id,
            conversation_id=conversation_id,
            entry_id=entry_id,
            error_type=error_type,
        )
        return entry_id
    except Exception as exc:
        logger.warning(
            "langgraph_dlq_db_persist_failed",
            company_id=company_id,
            error=str(exc)[:200],
        )
        return None


# ══════════════════════════════════════════════════════════════════
# QUERY / RETRY / RESOLVE
# ══════════════════════════════════════════════════════════════════


def get_dlq_entries(
    company_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    resolved: bool = False,
    error_type: str | None = None,
) -> List[Dict[str, Any]]:
    """Read DLQ entries from PostgreSQL for a given company.

    Args:
        company_id: Tenant identifier (BC-001)
        limit: Max entries to return (default 50)
        offset: Pagination offset
        resolved: If True, return resolved entries; if False, unresolved only
        error_type: Optional filter by error type

    Returns:
        List of DLQ entry dicts
    """
    try:
        from database.base import SessionLocal

        with SessionLocal() as db:
            query = db.query(GraphExecutionDLQ).filter(
                GraphExecutionDLQ.company_id == company_id,
            )

            if resolved:
                query = query.filter(GraphExecutionDLQ.resolved_at.isnot(None))
            else:
                query = query.filter(GraphExecutionDLQ.resolved_at.is_(None))

            if error_type:
                query = query.filter(GraphExecutionDLQ.error_type == error_type)

            query = query.order_by(GraphExecutionDLQ.created_at.desc())
            entries = query.offset(offset).limit(limit).all()

            return [
                {
                    "id": e.id,
                    "company_id": e.company_id,
                    "conversation_id": e.conversation_id,
                    "session_id": e.session_id,
                    "error": e.error,
                    "error_type": e.error_type,
                    "state_snapshot": _json.loads(e.state_snapshot) if e.state_snapshot else {},
                    "variant_tier": e.variant_tier,
                    "channel": e.channel,
                    "intent": e.intent,
                    "retried": e.retried,
                    "retry_count": e.retry_count,
                    "retry_succeeded": e.retry_succeeded,
                    "last_retry_at": e.last_retry_at.isoformat() if e.last_retry_at else None,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
                }
                for e in entries
            ]
    except Exception as exc:
        logger.error(
            "langgraph_dlq_get_entries_failed",
            company_id=company_id,
            error=str(exc)[:200],
        )
        return []


def retry_dlq_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    """Mark a DLQ entry as retried (increments retry_count, sets last_retry_at).

    This does NOT re-execute the graph — it only updates the record so that
    operators can track which entries have been manually replayed.

    Args:
        entry_id: The DLQ entry UUID

    Returns:
        Updated entry dict on success, None on failure
    """
    try:
        from database.base import SessionLocal

        with SessionLocal() as db:
            entry = db.query(GraphExecutionDLQ).filter(
                GraphExecutionDLQ.id == entry_id,
            ).first()

            if entry is None:
                logger.warning("langgraph_dlq_retry_entry_not_found", entry_id=entry_id)
                return None

            entry.retried = True
            entry.retry_count = (entry.retry_count or 0) + 1
            entry.last_retry_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                "langgraph_dlq_entry_retried",
                entry_id=entry_id,
                retry_count=entry.retry_count,
            )

            return {
                "id": entry.id,
                "retried": entry.retried,
                "retry_count": entry.retry_count,
                "last_retry_at": entry.last_retry_at.isoformat() if entry.last_retry_at else None,
            }
    except Exception as exc:
        logger.error(
            "langgraph_dlq_retry_failed",
            entry_id=entry_id,
            error=str(exc)[:200],
        )
        return None


def resolve_dlq_entry(entry_id: str, *, retry_succeeded: bool = True) -> Optional[Dict[str, Any]]:
    """Mark a DLQ entry as resolved.

    Sets resolved_at and optionally records whether the retry succeeded.

    Args:
        entry_id: The DLQ entry UUID
        retry_succeeded: Whether the retry was successful (default True)

    Returns:
        Updated entry dict on success, None on failure
    """
    try:
        from database.base import SessionLocal

        with SessionLocal() as db:
            entry = db.query(GraphExecutionDLQ).filter(
                GraphExecutionDLQ.id == entry_id,
            ).first()

            if entry is None:
                logger.warning("langgraph_dlq_resolve_entry_not_found", entry_id=entry_id)
                return None

            entry.resolved_at = datetime.now(timezone.utc)
            entry.retry_succeeded = retry_succeeded
            db.commit()

            logger.info(
                "langgraph_dlq_entry_resolved",
                entry_id=entry_id,
                retry_succeeded=retry_succeeded,
            )

            return {
                "id": entry.id,
                "resolved_at": entry.resolved_at.isoformat() if entry.resolved_at else None,
                "retry_succeeded": entry.retry_succeeded,
            }
    except Exception as exc:
        logger.error(
            "langgraph_dlq_resolve_failed",
            entry_id=entry_id,
            error=str(exc)[:200],
        )
        return None


def get_dlq_stats(company_id: str) -> Dict[str, Any]:
    """Return DLQ aggregate counts by error_type for a company.

    Also includes total counts for unresolved, retried, and resolved entries.

    Args:
        company_id: Tenant identifier (BC-001)

    Returns:
        Dict with 'by_error_type', 'total_unresolved', 'total_retried',
        'total_resolved' keys
    """
    try:
        from database.base import SessionLocal

        with SessionLocal() as db:
            # Count by error_type (unresolved only)
            rows = (
                db.query(
                    GraphExecutionDLQ.error_type,
                    func.count(GraphExecutionDLQ.id),
                )
                .filter(
                    GraphExecutionDLQ.company_id == company_id,
                    GraphExecutionDLQ.resolved_at.is_(None),
                )
                .group_by(GraphExecutionDLQ.error_type)
                .all()
            )
            by_error_type = {row[0] or "unknown": row[1] for row in rows}

            total_unresolved = (
                db.query(func.count(GraphExecutionDLQ.id))
                .filter(
                    GraphExecutionDLQ.company_id == company_id,
                    GraphExecutionDLQ.resolved_at.is_(None),
                )
                .scalar() or 0
            )

            total_retried = (
                db.query(func.count(GraphExecutionDLQ.id))
                .filter(
                    GraphExecutionDLQ.company_id == company_id,
                    GraphExecutionDLQ.retried.is_(True),
                    GraphExecutionDLQ.resolved_at.is_(None),
                )
                .scalar() or 0
            )

            total_resolved = (
                db.query(func.count(GraphExecutionDLQ.id))
                .filter(
                    GraphExecutionDLQ.company_id == company_id,
                    GraphExecutionDLQ.resolved_at.isnot(None),
                )
                .scalar() or 0
            )

            return {
                "by_error_type": by_error_type,
                "total_unresolved": total_unresolved,
                "total_retried": total_retried,
                "total_resolved": total_resolved,
            }
    except Exception as exc:
        logger.error(
            "langgraph_dlq_stats_failed",
            company_id=company_id,
            error=str(exc)[:200],
        )
        return {
            "by_error_type": {},
            "total_unresolved": 0,
            "total_retried": 0,
            "total_resolved": 0,
        }
