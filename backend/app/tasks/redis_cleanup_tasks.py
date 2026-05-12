"""
PARWA Redis Cleanup Tasks (Phase 6: Production Hardening)

Periodic Celery tasks for:
- Auditing Redis keys for orphans and missing TTLs
- Applying default TTLs to keys missing expiry
- Cleaning up orphaned keys that don't match known patterns

BC-001: company_id first parameter on all tenant-scoped operations.
BC-008: Never crash — all tasks handle errors gracefully.
BC-012: All timestamps UTC.

Beat schedule entries (add to celery_app.py):
    "redis-audit-hourly": {
        "task": "app.tasks.redis_cleanup_tasks.audit_redis_keys_task",
        "schedule": 3600.0,
    },
    "redis-fix-ttls-daily": {
        "task": "app.tasks.redis_cleanup_tasks.cleanup_expired_keys_task",
        "schedule": {"hour": 3, "minute": 15},
    },
    "redis-cleanup-orphans-weekly": {
        "task": "app.tasks.redis_cleanup_tasks.cleanup_orphaned_keys_task",
        "schedule": 604800.0,  # Weekly
        "kwargs": {"dry_run": True},
    },
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.tasks.celery_app import app
from app.tasks.base import ParwaBaseTask

logger = logging.getLogger("parwa.tasks.redis_cleanup")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    name="app.tasks.redis_cleanup_tasks.audit_redis_keys_task",
    max_retries=1,
    soft_time_limit=120,
    time_limit=180,
)
def audit_redis_keys_task(self) -> Dict[str, Any]:
    """Run a full Redis key audit and log results.

    Scans all Redis keys and reports:
    - Total key count
    - Keys without TTL (potential memory leaks)
    - Keys by namespace
    - Orphaned keys (don't match any known pattern)

    Returns:
        Dict with audit results
    """
    try:
        import asyncio
        from app.core.redis_key_manager import audit_all_keys

        async def _audit():
            from app.core.redis import get_redis
            client = await get_redis()
            return await audit_all_keys(client)

        # Run async audit
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(asyncio.run, _audit()).result(timeout=150)
        except RuntimeError:
            result = asyncio.run(_audit())

        # Log key findings
        total_keys = result.get("total_key_count", 0)
        keys_no_ttl = result.get("keys_without_ttl", 0)
        orphans = result.get("orphaned_key_count", 0)

        logger.info(
            "redis_audit_task_complete",
            extra={
                "total_keys": total_keys,
                "keys_without_ttl": keys_no_ttl,
                "orphaned_keys": orphans,
                "namespaces": result.get("keys_by_namespace", {}),
            },
        )

        # Alert on concerning findings
        if orphans > 50:
            logger.warning(
                "redis_audit_high_orphan_count",
                extra={
                    "orphaned_keys": orphans,
                    "sample": result.get("orphaned_keys", [])[:5],
                    "recommendation": (
                        "Run cleanup_orphaned_keys_task with dry_run=True "
                        "to preview deletions"
                    ),
                },
            )

        if keys_no_ttl > 100:
            logger.warning(
                "redis_audit_many_keys_without_ttl",
                extra={
                    "keys_without_ttl": keys_no_ttl,
                    "recommendation": (
                        "Run cleanup_expired_keys_task with dry_run=False "
                        "to apply default TTLs"
                    ),
                },
            )

        return {
            "status": "success",
            "total_keys": total_keys,
            "keys_without_ttl": keys_no_ttl,
            "orphaned_keys": orphans,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(
            "redis_audit_task_failed",
            extra={"error": str(exc)[:500]},
        )
        return {
            "status": "error",
            "error": str(exc)[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.task(
    base=ParwaBaseTask,
    bind=True,
    name="app.tasks.redis_cleanup_tasks.cleanup_expired_keys_task",
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
)
def cleanup_expired_keys_task(self, dry_run: bool = True) -> Dict[str, Any]:
    """Apply default TTLs to keys that are missing them.

    Scans all Redis keys and applies the namespace-appropriate default
    TTL to any key that has no expiry set.

    Args:
        dry_run: If True, only report what would be changed (default).
                 Set to False to actually apply TTLs.

    Returns:
        Dict with keys_fixed count and details
    """
    try:
        import asyncio
        from app.core.redis_key_manager import fix_missing_ttls

        async def _fix():
            from app.core.redis import get_redis
            client = await get_redis()
            return await fix_missing_ttls(client, dry_run=dry_run)

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(asyncio.run, _fix()).result(timeout=300)
        except RuntimeError:
            result = asyncio.run(_fix())

        keys_fixed = result.get("keys_fixed", 0)

        logger.info(
            "redis_ttl_fix_task_complete",
            extra={
                "dry_run": dry_run,
                "keys_scanned": result.get("keys_scanned", 0),
                "keys_fixed": keys_fixed,
            },
        )

        return {
            "status": "success",
            "dry_run": dry_run,
            "keys_fixed": keys_fixed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(
            "redis_ttl_fix_task_failed",
            extra={"error": str(exc)[:500]},
        )
        return {
            "status": "error",
            "error": str(exc)[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.task(
    base=ParwaBaseTask,
    bind=True,
    name="app.tasks.redis_cleanup_tasks.cleanup_orphaned_keys_task",
    max_retries=0,  # Destructive — don't auto-retry
    soft_time_limit=600,
    time_limit=720,
)
def cleanup_orphaned_keys_task(
    self,
    dry_run: bool = True,
    max_keys: int = 1000,
) -> Dict[str, Any]:
    """Remove keys that don't match any known pattern.

    CAUTION: This task can DELETE keys. Always run with dry_run=True
    first to preview what would be deleted.

    An orphaned key is one that:
    - Does not start with "parwa:" (non-standard prefix)
    - OR starts with "parwa:" but doesn't match any known namespace

    Args:
        dry_run: If True, only report orphans without deleting (default).
                 Set to False to actually delete orphaned keys.
        max_keys: Maximum number of keys to delete in one run (safety cap).

    Returns:
        Dict with keys_deleted count and sample of deleted keys
    """
    try:
        import asyncio

        async def _cleanup():
            from app.core.redis import get_redis
            client = await get_redis()

            # First audit to find orphans
            from app.core.redis_key_manager import audit_all_keys
            audit = await audit_all_keys(client)

            orphaned_keys = audit.get("orphaned_keys", [])
            capped_keys = orphaned_keys[:max_keys]

            if dry_run:
                return {
                    "dry_run": True,
                    "orphaned_key_count": len(orphaned_keys),
                    "would_delete_count": len(capped_keys),
                    "sample_keys": capped_keys[:20],
                    "total_key_count": audit.get("total_key_count", 0),
                }

            # Actually delete orphaned keys
            deleted = 0
            for key in capped_keys:
                try:
                    await client.delete(key)
                    deleted += 1
                except Exception:
                    pass

            return {
                "dry_run": False,
                "orphaned_key_count": len(orphaned_keys),
                "keys_deleted": deleted,
                "sample_deleted": capped_keys[:20],
                "total_key_count": audit.get("total_key_count", 0),
            }

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(asyncio.run, _cleanup()).result(timeout=600)
        except RuntimeError:
            result = asyncio.run(_cleanup())

        action = "previewed" if dry_run else "deleted"
        count = result.get("would_delete_count" if dry_run else "keys_deleted", 0)

        logger.info(
            "redis_orphan_cleanup_task_complete",
            extra={
                "dry_run": dry_run,
                f"keys_{action}": count,
                "total_orphans": result.get("orphaned_key_count", 0),
            },
        )

        return {
            "status": "success",
            **result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(
            "redis_orphan_cleanup_task_failed",
            extra={"error": str(exc)[:500]},
        )
        return {
            "status": "error",
            "error": str(exc)[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
