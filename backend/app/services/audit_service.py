"""
PARWA Audit Service

Writes audit trail entries to the audit_trail table.
Every significant action (create, update, delete, login, etc.)
must be logged through this service.

Audit trail fields (from database/models/integration.py):
- id: UUID primary key
- company_id: Tenant ID (BC-001)
- actor_id: Who performed the action (user ID or system)
- actor_type: Type of actor (user, system, api_key)
- action: What was done (create, update, delete, login, etc.)
- resource_type: What was affected (ticket, user, subscription, etc.)
- resource_id: ID of the affected resource
- old_value: Previous value (for updates)
- new_value: New value (for creates/updates)
- ip_address: Client IP address
- user_agent: Client user agent string
- created_at: Timestamp
"""

import enum
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.audit")

# Redis queue key for async audit entries (system-level queue;
# each entry already carries company_id for BC-001 isolation)
AUDIT_REDIS_QUEUE = "parwa:audit:queue"

# Default retention period for audit entries (days)
AUDIT_RETENTION_DAYS = 365

# Maximum entries to process per Celery batch flush
AUDIT_BATCH_SIZE = 100


class ActorType(str, enum.Enum):
    """Types of actors that can perform audited actions."""

    USER = "user"
    SYSTEM = "system"
    API_KEY = "api_key"


class AuditAction(str, enum.Enum):
    """Standard audit action types."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    SETTINGS_CHANGE = "settings_change"
    PERMISSION_CHANGE = "permission_change"
    API_KEY_CREATE = "api_key_create"
    API_KEY_ROTATE = "api_key_rotate"
    API_KEY_REVOKE = "api_key_revoke"
    WEBHOOK_DELIVERED = "webhook_delivered"
    WEBHOOK_FAILED = "webhook_failed"


VALID_ACTOR_TYPES = {t.value for t in ActorType}


def validate_actor_type(actor_type: str) -> str:
    """Validate that actor_type is a known value.

    Args:
        actor_type: String to validate.

    Returns:
        Validated actor_type string.

    Raises:
        ValueError: If actor_type is not a valid ActorType.
    """
    if not actor_type or actor_type not in VALID_ACTOR_TYPES:
        raise ValueError(
            f"Invalid actor_type '{actor_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ACTOR_TYPES))}"
        )
    return actor_type


class AuditEntry:
    """Represents a single audit trail entry.

    This is the data structure for creating audit entries.
    The actual database write happens through the audit_service functions.
    """

    def __init__(
        self,
        company_id: str,
        actor_id: Optional[str] = None,
        actor_type: str = ActorType.SYSTEM.value,
        action: str = "unknown",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        # Validate company_id first (BC-001 — multi-tenant isolation)
        if not company_id or not isinstance(company_id, str):
            raise ValueError(
                "company_id is required and must be a "
                "non-empty string (BC-001)"
            )
        if len(company_id) > 128:
            raise ValueError("company_id must not exceed 128 characters")
        validate_actor_type(actor_type)
        self.id = str(uuid.uuid4())
        self.company_id = company_id
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.old_value = old_value
        self.new_value = new_value
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert to dictionary (for JSON serialization or DB insert)."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        """Serialize entry to JSON string for Redis queue.

        Datetime is converted to ISO-8601 string.

        Returns:
            JSON string representation of the audit entry.
        """
        data = self.to_dict()
        # Convert datetime to ISO string for JSON serialization
        if isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        return json.dumps(data)


def create_audit_entry(
    company_id: str,
    actor_id: Optional[str] = None,
    actor_type: str = ActorType.SYSTEM.value,
    action: str = "unknown",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditEntry:
    """Create an audit trail entry.

    This is the primary interface for creating audit entries.
    The entry is returned as an AuditEntry object that can be
    serialized to dict for database insertion.

    Args:
        company_id: Tenant ID (BC-001 — required for multi-tenant isolation).
        actor_id: ID of the user/system/api_key performing the action.
        actor_type: Type of actor (user, system, api_key).
        action: What action was performed.
        resource_type: Type of resource affected.
        resource_id: ID of the specific resource.
        old_value: Previous value (for updates).
        new_value: New value (for creates/updates).
        ip_address: Client IP address.
        user_agent: Client user agent.

    Returns:
        AuditEntry object ready for serialization.

    Raises:
        ValueError: If company_id is missing or actor_type is invalid.
    """
    if not company_id:
        raise ValueError("company_id is required for audit entries (BC-001)")

    return AuditEntry(
        company_id=company_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_audit(
    company_id: str,
    actor_id: Optional[str] = None,
    actor_type: str = ActorType.SYSTEM.value,
    action: str = "unknown",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db=None,
) -> dict:
    """Create audit entry and persist to database.

    Convenience function that creates an AuditEntry, persists
    it to the audit_trail table if a DB session is provided,
    and returns the entry as a dict.

    BC-012: Audit trail must be recorded for all write operations.

    Args:
        Same as create_audit_entry(), plus:
        db: Optional SQLAlchemy Session. If provided, the entry
            is written to the audit_trail table.

    Returns:
        Dictionary with all audit fields.
    """
    entry = create_audit_entry(
        company_id=company_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    entry_dict = entry.to_dict()

    if db is not None:
        try:
            from database.models.integration import AuditTrail

            record = AuditTrail(
                id=entry_dict["id"],
                company_id=entry_dict["company_id"],
                actor_id=entry_dict["actor_id"],
                actor_type=entry_dict["actor_type"],
                action=entry_dict["action"],
                resource_type=entry_dict["resource_type"],
                resource_id=entry_dict["resource_id"],
                old_value=entry_dict["old_value"],
                new_value=entry_dict["new_value"],
                ip_address=entry_dict["ip_address"],
                user_agent=entry_dict["user_agent"],
                created_at=entry_dict["created_at"],
            )
            db.add(record)
            # CRITICAL FIX: Use flush() not commit() to avoid
            # prematurely committing the caller's transaction.
            # The caller's transaction manager controls the commit.
            db.flush()
        except Exception:
            # Audit logging must never break the main operation.
            # Log but don't raise.
            try:
                db.rollback()
            except Exception:
                pass

    return entry_dict


# ── Async audit logging via Redis ──────────────────────────────────


async def async_log_audit(
    redis_client,
    company_id: str,
    actor_id: Optional[str] = None,
    actor_type: str = "system",
    action: str = "unknown",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Log an audit entry asynchronously via Redis queue.

    Creates an AuditEntry, serializes to JSON, and pushes to the
    Redis list ``parwa:audit:queue``. A Celery periodic task
    (``process_audit_queue``) flushes entries from this queue
    into the database in batches.

    This is fire-and-forget — the entry dict is returned
    immediately regardless of whether the Redis push succeeds.
    If Redis is down, a warning is logged and the function
    returns the entry dict without blocking the caller.

    BC-012: Audit failures must never break main operations.

    Args:
        redis_client: Async Redis client (e.g. from ``get_redis()``).
        company_id: Tenant ID (BC-001 — required).
        actor_id: ID of the user/system/api_key performing the action.
        actor_type: Type of actor (user, system, api_key).
        action: What action was performed.
        resource_type: Type of resource affected.
        resource_id: ID of the specific resource.
        old_value: Previous value (for updates).
        new_value: New value (for creates/updates).
        ip_address: Client IP address.
        user_agent: Client user agent.

    Returns:
        Dictionary with all audit fields (same shape as ``log_audit()``).
    """
    entry = create_audit_entry(
        company_id=company_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    entry_dict = entry.to_dict()

    try:
        payload = entry.to_json()
        await redis_client.rpush(AUDIT_REDIS_QUEUE, payload)
    except Exception as exc:
        # BC-012: Never block main flow on audit failure.
        logger.warning(
            "async_log_audit: failed to push to Redis queue: %s",
            exc,
        )

    return entry_dict


# ── Celery task: batch flush Redis audit queue to DB ──────────────


def process_audit_queue() -> dict:
    """Flush pending audit entries from Redis queue to database.

    Pops up to ``AUDIT_BATCH_SIZE`` (100) entries from the Redis
    list ``parwa:audit:queue``, deserializes each, and batch-inserts
    into the ``audit_trail`` table.

    Designed to run as a Celery periodic task on the ``analytics``
    queue every 60 seconds.

    On failure, unprocessed entries remain in Redis and will be
    retried on the next run (at-least-once delivery semantics).

    Returns:
        Dict with keys ``status``, ``processed`` (count), and
        optional ``error``.
    """
    processed = 0
    try:
        from database.base import SessionLocal

        db = SessionLocal()
        try:
            # Synchronous Redis for Celery worker context
            import redis as sync_redis
            from backend.app.config import get_settings

            settings = get_settings()
            r = sync_redis.from_url(
                settings.CELERY_BROKER_URL,
                decode_responses=True,
                socket_timeout=5,
            )

            entries: List[dict] = []
            for _ in range(AUDIT_BATCH_SIZE):
                raw = r.lpop(AUDIT_REDIS_QUEUE)
                if raw is None:
                    break
                try:
                    entries.append(json.loads(raw))
                except (json.JSONDecodeError, TypeError) as parse_err:
                    logger.warning(
                        "process_audit_queue: skipping malformed entry: %s",
                        parse_err,
                    )

            if not entries:
                return {"status": "ok", "processed": 0}

            from database.models.integration import AuditTrail

            for entry_data in entries:
                # Parse ISO datetime back if present
                created_at = entry_data.get("created_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except (ValueError, TypeError):
                        created_at = datetime.now(timezone.utc)

                record = AuditTrail(
                    id=entry_data.get("id", str(uuid.uuid4())),
                    company_id=entry_data.get("company_id"),
                    actor_id=entry_data.get("actor_id"),
                    actor_type=entry_data.get("actor_type", "system"),
                    action=entry_data.get("action", "unknown"),
                    resource_type=entry_data.get("resource_type"),
                    resource_id=entry_data.get("resource_id"),
                    old_value=entry_data.get("old_value"),
                    new_value=entry_data.get("new_value"),
                    ip_address=entry_data.get("ip_address"),
                    user_agent=entry_data.get("user_agent"),
                    created_at=created_at,
                )
                db.add(record)
                processed += 1

            db.commit()
            logger.info(
                "process_audit_queue: flushed %d entries to DB",
                processed,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "process_audit_queue failed error=%s",
            exc,
        )
        return {"status": "failed", "processed": processed, "error": str(exc)[:200]}

    return {"status": "ok", "processed": processed}


# ── Audit trail query ─────────────────────────────────────────────


def query_audit_trail(
    db,
    company_id: str,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    offset: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """Query the audit trail with filtering and pagination.

    All queries are scoped to ``company_id`` (BC-001).

    Args:
        db: SQLAlchemy database session.
        company_id: Tenant ID (BC-001 — required).
        actor_type: Filter by actor type (user, system, api_key).
        action: Filter by action name (create, update, etc.).
        resource_type: Filter by resource type (ticket, user, etc.).
        resource_id: Filter by specific resource ID.
        actor_id: Filter by actor ID.
        date_from: Include entries created at or after this datetime.
        date_to: Include entries created at or before this datetime.
        offset: Pagination offset (records to skip).
        limit: Pagination limit (max records to return).

    Returns:
        Tuple of ``(items, total)`` where ``items`` is a list of dicts
        and ``total`` is the total matching count for pagination.
    """
    from database.models.integration import AuditTrail
    from shared.utils.pagination import parse_pagination

    if not company_id:
        raise ValueError("company_id is required for audit queries (BC-001)")

    params = parse_pagination(offset=offset, limit=limit)

    query = db.query(AuditTrail).filter(AuditTrail.company_id == company_id)

    if actor_type is not None:
        query = query.filter(AuditTrail.actor_type == actor_type)
    if action is not None:
        query = query.filter(AuditTrail.action == action)
    if resource_type is not None:
        query = query.filter(AuditTrail.resource_type == resource_type)
    if resource_id is not None:
        query = query.filter(AuditTrail.resource_id == resource_id)
    if actor_id is not None:
        query = query.filter(AuditTrail.actor_id == actor_id)
    if date_from is not None:
        query = query.filter(AuditTrail.created_at >= date_from)
    if date_to is not None:
        query = query.filter(AuditTrail.created_at <= date_to)

    total = query.count()
    records = (
        query.order_by(AuditTrail.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
        .all()
    )

    items = []
    for rec in records:
        items.append({
            "id": rec.id,
            "company_id": rec.company_id,
            "actor_id": rec.actor_id,
            "actor_type": rec.actor_type,
            "action": rec.action,
            "resource_type": rec.resource_type,
            "resource_id": rec.resource_id,
            "old_value": rec.old_value,
            "new_value": rec.new_value,
            "ip_address": rec.ip_address,
            "user_agent": rec.user_agent,
            "created_at": (
                rec.created_at.isoformat()
                if rec.created_at else None
            ),
        })

    return items, total


# ── Audit trail export ────────────────────────────────────────────


def export_audit_trail(
    db,
    company_id: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    format: str = "json",
) -> List[Dict[str, Any]]:
    """Export audit trail entries for compliance reporting.

    Returns all matching audit entries for a company in the given
    date range. Dates in the returned dicts are ISO-8601 formatted
    strings.

    BC-001: Always filtered by company_id.
    BC-010: Supports compliance exports.

    Args:
        db: SQLAlchemy database session.
        company_id: Tenant ID (BC-001 — required).
        date_from: Include entries created at or after this datetime.
        date_to: Include entries created at or before this datetime.
        format: Export format — currently only ``"json"`` is supported.
            CSV can be added later.

    Returns:
        List of dicts with ISO-formatted date strings.

    Raises:
        ValueError: If company_id is missing or format is unsupported.
    """
    from database.models.integration import AuditTrail

    if not company_id:
        raise ValueError("company_id is required for audit export (BC-001)")

    if format not in ("json",):
        raise ValueError(
            f"Unsupported export format '{format}'. "
            f"Only 'json' is currently supported."
        )

    query = db.query(AuditTrail).filter(AuditTrail.company_id == company_id)

    if date_from is not None:
        query = query.filter(AuditTrail.created_at >= date_from)
    if date_to is not None:
        query = query.filter(AuditTrail.created_at <= date_to)

    records = query.order_by(AuditTrail.created_at.asc()).all()

    items = []
    for rec in records:
        items.append({
            "id": rec.id,
            "company_id": rec.company_id,
            "actor_id": rec.actor_id,
            "actor_type": rec.actor_type,
            "action": rec.action,
            "resource_type": rec.resource_type,
            "resource_id": rec.resource_id,
            "old_value": rec.old_value,
            "new_value": rec.new_value,
            "ip_address": rec.ip_address,
            "user_agent": rec.user_agent,
            "created_at": (
                rec.created_at.isoformat()
                if rec.created_at else None
            ),
        })

    return items


# ── Audit statistics ──────────────────────────────────────────────


def get_audit_stats(
    db,
    company_id: str,
    days: int = 30,
) -> Dict[str, Any]:
    """Retrieve aggregated audit statistics for a company.

    Computes action-type distribution, actor-type distribution,
    most active actors, and recent activity counts.

    BC-001: Always filtered by company_id.

    Args:
        db: SQLAlchemy database session.
        company_id: Tenant ID (BC-001 — required).
        days: Look-back window in days (default 30).

    Returns:
        Dict with keys:
        - ``action_counts``: dict mapping action → count
        - ``actor_type_counts``: dict mapping actor_type → count
        - ``most_active_actors``: list of {actor_id, actor_type, count}
          sorted descending (top 10)
        - ``recent_24h_count``: number of entries in the last 24 hours
        - ``total_count``: total entries within the look-back window
        - ``period_days``: the actual look-back period used

    Raises:
        ValueError: If company_id is missing.
    """
    from sqlalchemy import func

    from database.models.integration import AuditTrail

    if not company_id:
        raise ValueError("company_id is required for audit stats (BC-001)")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base_query = db.query(AuditTrail).filter(
        AuditTrail.company_id == company_id,
        AuditTrail.created_at >= cutoff,
    )

    total_count = base_query.count()

    # Count by action type
    action_rows = (
        db.query(AuditTrail.action, func.count(AuditTrail.id))
        .filter(
            AuditTrail.company_id == company_id,
            AuditTrail.created_at >= cutoff,
        )
        .group_by(AuditTrail.action)
        .all()
    )
    action_counts = {row[0]: row[1] for row in action_rows}

    # Count by actor_type
    actor_type_rows = (
        db.query(AuditTrail.actor_type, func.count(AuditTrail.id))
        .filter(
            AuditTrail.company_id == company_id,
            AuditTrail.created_at >= cutoff,
        )
        .group_by(AuditTrail.actor_type)
        .all()
    )
    actor_type_counts = {row[0]: row[1] for row in actor_type_rows}

    # Most active actors (top 10)
    actor_rows = (
        db.query(
            AuditTrail.actor_id,
            AuditTrail.actor_type,
            func.count(AuditTrail.id).label("cnt"),
        )
        .filter(
            AuditTrail.company_id == company_id,
            AuditTrail.created_at >= cutoff,
        )
        .group_by(AuditTrail.actor_id, AuditTrail.actor_type)
        .order_by(func.count(AuditTrail.id).desc())
        .limit(10)
        .all()
    )
    most_active_actors = [
        {"actor_id": row[0], "actor_type": row[1], "count": row[2]}
        for row in actor_rows
    ]

    # Recent activity: last 24 hours
    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_24h_count = (
        db.query(func.count(AuditTrail.id))
        .filter(
            AuditTrail.company_id == company_id,
            AuditTrail.created_at >= recent_cutoff,
        )
        .scalar()
        or 0
    )

    return {
        "action_counts": action_counts,
        "actor_type_counts": actor_type_counts,
        "most_active_actors": most_active_actors,
        "recent_24h_count": recent_24h_count,
        "total_count": total_count,
        "period_days": days,
    }


# ── Retention cleanup ─────────────────────────────────────────────


def cleanup_old_audit_entries(
    db=None,
    company_id: Optional[str] = None,
    retention_days: int = AUDIT_RETENTION_DAYS,
) -> int:
    """Delete audit trail entries older than the retention period.

    When called without ``db``, creates its own session (suitable for
    periodic task invocation). When called with a session, the caller
    controls the transaction.

    BC-001: If company_id is provided, only that tenant's entries are
    cleaned up. If None, all tenants are cleaned (used by the
    daily periodic task).

    Args:
        db: Optional SQLAlchemy session. If None, a session is
            created and closed internally.
        company_id: Tenant ID to scope the cleanup. If None,
            cleans up entries for all tenants.
        retention_days: Number of days to retain entries
            (default 365).

    Returns:
        Number of deleted entries.
    """
    from database.models.integration import AuditTrail

    owns_session = False
    if db is None:
        from database.base import SessionLocal
        db = SessionLocal()
        owns_session = True

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        query = db.query(AuditTrail).filter(AuditTrail.created_at < cutoff)

        if company_id is not None:
            query = query.filter(AuditTrail.company_id == company_id)

        # Delete in batches to avoid long-running transactions
        total_deleted = 0
        batch_size = 1000
        while True:
            batch_ids = (
                query.with_entities(AuditTrail.id)
                .limit(batch_size)
                .all()
            )
            if not batch_ids:
                break
            ids_to_delete = [bid[0] for bid in batch_ids]
            db.query(AuditTrail).filter(
                AuditTrail.id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            total_deleted += len(ids_to_delete)

        if owns_session:
            db.commit()
            logger.info(
                "cleanup_old_audit_entries: deleted %d entries "
                "(retention=%d days%s)",
                total_deleted,
                retention_days,
                f", company_id={company_id}" if company_id else " (all tenants)",
            )

        return total_deleted
    except Exception as exc:
        if owns_session:
            db.rollback()
        logger.warning(
            "cleanup_old_audit_entries failed: %s",
            exc,
        )
        if owns_session:
            raise
        return 0
    finally:
        if owns_session:
            db.close()
