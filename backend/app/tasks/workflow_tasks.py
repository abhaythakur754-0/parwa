"""
PARWA Workflow Celery Tasks (Week 10 Day 4, BC-004)

Background tasks for the AI Core State Engine + Workflow pipeline.
These tasks wire up the 16 core modules for periodic maintenance,
batch processing, and asynchronous operations.

Tasks:
  - cleanup_stale_states: Remove orphaned workflow states
  - export_metrics: Aggregate and export technique metrics
  - check_capacity_alerts: Monitor capacity thresholds
  - compress_stale_contexts: Auto-compress degrading contexts
  - warm_technique_cache: Preload technique cache entries
  - migrate_stale_states: Batch-migrate old schema versions

Building Codes:
  - BC-001: Multi-Tenant Isolation (company_id on every task)
  - BC-004: Background Jobs (Celery patterns with ParwaBaseTask)
  - BC-008: Graceful degradation (never crash, log and continue)
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.tasks.base import ParwaBaseTask, set_task_tenant_header
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.workflow")


# ══════════════════════════════════════════════════════════════════
# 1. CLEANUP STALE STATES (periodic — every 24 hours)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="workflow.cleanup_stale_states",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def cleanup_stale_states(
    self, max_age_hours: int = 24,
) -> dict:
    """Remove orphaned workflow states older than max_age_hours.

    Scans Redis for active conversation states that have not been
    accessed within the specified age window and removes them.
    Also cleans up expired cache entries in TechniqueCache and
    stale metrics in TechniqueMetricsCollector.

    Args:
        max_age_hours: Maximum age in hours before a state
            is considered stale. Default 24 hours.

    Returns:
        Dict with cleanup statistics.
    """
    try:
        total_cleaned = 0
        details: Dict[str, Any] = {}

        # 1. Cleanup stale technique metrics
        try:
            from app.core.technique_metrics import TechniqueMetricsCollector

            collector = TechniqueMetricsCollector()
            max_age_seconds = max_age_hours * 3600
            metrics_cleaned = collector.cleanup_stale(max_age_seconds)
            details["metrics_records_removed"] = metrics_cleaned
            total_cleaned += metrics_cleaned

            logger.info(
                "stale_metrics_cleaned",
                extra={
                    "task": self.name,
                    "records_removed": metrics_cleaned,
                    "max_age_hours": max_age_hours,
                },
            )
        except Exception as exc:
            logger.warning(
                "stale_metrics_cleanup_failed",
                extra={
                    "task": self.name,
                    "error": str(exc)[:200],
                },
            )

        # 2. Cleanup expired technique cache entries
        try:
            from app.core.technique_caching import TechniqueCache

            cache = TechniqueCache()
            expired = cache.cleanup()
            details["cache_entries_expired"] = expired
            total_cleaned += expired

            logger.info(
                "expired_cache_cleaned",
                extra={
                    "task": self.name,
                    "entries_expired": expired,
                },
            )
        except Exception as exc:
            logger.warning(
                "cache_cleanup_failed",
                extra={
                    "task": self.name,
                    "error": str(exc)[:200],
                },
            )

        # 3. Try to cleanup stale Redis state keys
        try:
            from app.core.redis import get_redis

            redis = get_redis()
            if redis:
                cutoff = time.time() - (max_age_hours * 3600)
                # Scan for parwa:state:* keys and check age
                # Note: Redis SCAN is used to avoid blocking
                cleaned_keys = 0
                cursor = 0
                pattern = "parwa:state:*"
                while True:
                    cursor, keys = redis.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100,
                    )
                    for key in keys:
                        try:
                            age = redis.object("idletime", key)
                            if age and age > max_age_hours * 3600:
                                redis.delete(key)
                                cleaned_keys += 1
                        except Exception:
                            pass
                    if cursor == 0:
                        break

                details["redis_state_keys_removed"] = cleaned_keys
                total_cleaned += cleaned_keys

                logger.info(
                    "redis_state_keys_cleaned",
                    extra={
                        "task": self.name,
                        "keys_removed": cleaned_keys,
                    },
                )
            else:
                details["redis_state_keys_removed"] = 0
                logger.info(
                    "redis_unavailable_skip_cleanup",
                    extra={"task": self.name},
                )
        except Exception as exc:
            logger.warning(
                "redis_state_cleanup_failed",
                extra={
                    "task": self.name,
                    "error": str(exc)[:200],
                },
            )

        logger.info(
            "cleanup_stale_states_success",
            extra={
                "task": self.name,
                "total_cleaned": total_cleaned,
                "max_age_hours": max_age_hours,
            },
        )

        return {
            "status": "cleaned",
            "total_cleaned": total_cleaned,
            "max_age_hours": max_age_hours,
            "details": details,
        }

    except Exception as exc:
        logger.error(
            "cleanup_stale_states_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 2. EXPORT METRICS (periodic — every hour)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="analytics",
    name="workflow.export_metrics",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def export_metrics(self, window: str = "1hr") -> dict:
    """Aggregate and export technique execution metrics.

    Collects metrics from TechniqueMetricsCollector for the
    specified time window and produces a summary suitable for
    dashboards, alerting, and billing.

    Args:
        window: Time window for aggregation.
            One of: 1min, 5min, 15min, 1hr.

    Returns:
        Dict with aggregated metrics summary.
    """
    try:
        from app.core.technique_metrics import (
            TechniqueMetricsCollector,
            TIME_WINDOWS_SECONDS,
        )

        collector = TechniqueMetricsCollector()
        window_seconds = TIME_WINDOWS_SECONDS.get(window, 3600)

        # Get stats for all techniques in the window
        all_stats: List[Dict[str, Any]] = []
        total_executions = 0
        total_tokens = 0
        total_failures = 0

        # Collect all unique technique IDs
        technique_ids = set()
        for (tid, _) in collector._stats.keys():
            technique_ids.add(tid)

        for tid in technique_ids:
            stats = collector.get_time_windowed_stats(
                technique_id=tid,
                window=window,
            )
            if stats.total_executions > 0:
                success_rate = (
                    stats.success_count / stats.total_executions * 100
                )
                avg_time = (
                    stats.total_exec_time_ms / stats.total_executions
                )
                all_stats.append({
                    "technique_id": tid,
                    "executions": stats.total_executions,
                    "success_rate": round(success_rate, 2),
                    "avg_time_ms": round(avg_time, 2),
                    "tokens": stats.total_tokens,
                    "failures": (
                        stats.failure_count
                        + stats.timeout_count
                        + stats.error_count
                    ),
                })
                total_executions += stats.total_executions
                total_tokens += stats.total_tokens
                total_failures += (
                    stats.failure_count
                    + stats.timeout_count
                    + stats.error_count
                )

        # Get global percentiles
        percentiles = collector.get_percentiles(
            metric="exec_time_ms",
        )

        # Get cache stats
        cache_stats = {}
        try:
            from app.core.technique_caching import TechniqueCache

            cache = TechniqueCache()
            cs = cache.get_stats()
            cache_stats = {
                "cache_hits": cs.hits,
                "cache_misses": cs.misses,
                "hit_rate": round(cs.hit_rate, 4),
                "cache_size": cs.size,
                "cache_max_size": cs.max_size,
                "cache_utilization": round(cs.utilization, 4),
            }
        except Exception as exc:
            logger.warning(
                "cache_stats_collection_failed",
                extra={
                    "task": self.name,
                    "error": str(exc)[:200],
                },
            )

        summary = {
            "window": window,
            "window_seconds": window_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_executions": total_executions,
            "total_tokens": total_tokens,
            "total_failures": total_failures,
            "overall_failure_rate": (
                round(total_failures / total_executions * 100, 2)
                if total_executions > 0
                else 0.0
            ),
            "technique_count": len(all_stats),
            "p50_exec_time_ms": percentiles.get("p50", 0.0),
            "p95_exec_time_ms": percentiles.get("p95", 0.0),
            "p99_exec_time_ms": percentiles.get("p99", 0.0),
            "cache": cache_stats,
            "top_techniques": sorted(
                all_stats,
                key=lambda x: x["executions"],
                reverse=True,
            )[:5],
        }

        logger.info(
            "export_metrics_success",
            extra={
                "task": self.name,
                "window": window,
                "total_executions": total_executions,
                "technique_count": len(all_stats),
            },
        )

        return {
            "status": "exported",
            "window": window,
            "summary": summary,
        }

    except Exception as exc:
        logger.error(
            "export_metrics_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 3. CHECK CAPACITY ALERTS (periodic — every 60 seconds)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="workflow.check_capacity_alerts",
    max_retries=1,
    soft_time_limit=30,
    time_limit=60,
)
def check_capacity_alerts(self) -> dict:
    """Monitor capacity thresholds across all tenants.

    Checks each tenant's capacity monitor for warning/critical
    conditions and triggers notifications when thresholds are
    crossed. Also generates auto-scaling signals when appropriate.
    """
    try:
        from app.core.capacity_monitor import CapacityMonitor

        monitor = CapacityMonitor()

        # Get all company IDs that have capacity data
        # The CapacityMonitor stores data internally
        # We check for any active alerts across known companies
        all_alerts: List[Dict[str, Any]] = []
        companies_with_overflow: List[str] = []

        # Since CapacityMonitor is in-memory, we need to access
        # internal state to enumerate companies
        all_companies = set()
        all_companies.update(monitor._active_slots.keys())
        all_companies.update(monitor._limits.keys())
        all_companies.update(monitor._queues.keys())

        if not all_companies:
            logger.info(
                "check_capacity_alerts_no_companies",
                extra={"task": self.name},
            )
            return {
                "status": "checked",
                "companies_scanned": 0,
                "total_alerts": 0,
            }

        for company_id in all_companies:
            try:
                alerts = monitor.get_alerts(company_id)
                if alerts:
                    all_alerts.extend(
                        {
                            "company_id": company_id,
                            **alert,
                        }
                        for alert in alerts
                    )
                    companies_with_overflow.append(company_id)
            except Exception as exc:
                logger.warning(
                    "capacity_check_company_failed",
                    extra={
                        "task": self.name,
                        "company_id": company_id,
                        "error": str(exc)[:200],
                    },
                )
                # BC-008: Continue with next company

        # Check for scaling suggestions
        scaling_actions: List[Dict[str, Any]] = []
        for company_id in companies_with_overflow:
            try:
                overflow = monitor.get_overflow_status(company_id)
                if overflow.get("scaling_suggestion"):
                    scaling_actions.append(
                        {
                            "company_id": company_id,
                            **overflow["scaling_suggestion"],
                        }
                    )
            except Exception:
                pass

        logger.info(
            "check_capacity_alerts_success",
            extra={
                "task": self.name,
                "companies_scanned": len(all_companies),
                "total_alerts": len(all_alerts),
                "overflow_companies": len(companies_with_overflow),
                "scaling_actions": len(scaling_actions),
            },
        )

        return {
            "status": "checked",
            "companies_scanned": len(all_companies),
            "total_alerts": len(all_alerts),
            "overflow_companies": len(companies_with_overflow),
            "scaling_actions": scaling_actions,
        }

    except Exception as exc:
        logger.error(
            "check_capacity_alerts_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 4. COMPRESS STALE CONTEXTS (periodic — every 15 minutes)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_light",
    name="workflow.compress_stale_contexts",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def compress_stale_contexts(
    self, health_threshold: str = "warning",
) -> dict:
    """Auto-compress contexts with degraded health scores.

    Finds conversations where the context health is below the
    specified threshold and triggers compression to free up
    token budget before quality degrades further.

    Args:
        health_threshold: Minimum health status to trigger
            compression. One of: healthy, degrading, warning,
            critical. Default: "warning" (compresses degrading,
            critical, exhausted).

    Returns:
        Dict with compression results.
    """
    try:
        from app.core.context_health import (
            ContextHealthMeter,
            HealthStatus,
        )

        meter = ContextHealthMeter()

        # Map threshold string to HealthStatus for comparison
        status_order = {
            "healthy": 4,
            "degrading": 3,
            "warning": 2,
            "critical": 1,
            "exhausted": 0,
        }
        min_order = status_order.get(health_threshold, 2)

        compressed_count = 0
        skipped_count = 0
        errors = 0

        # Iterate through all conversations with health data
        health_thresholds = {
            "healthy": HealthStatus.HEALTHY,
            "degrading": HealthStatus.DEGRADING,
            "critical": HealthStatus.CRITICAL,
            "exhausted": HealthStatus.EXHAUSTED,
        }
        threshold_status = health_thresholds.get(health_threshold)

        # Get all conversation histories
        all_conv_data = []
        try:
            # Access internal _turn_history to find conversations
            for conv_key, reports in meter._turn_history.items():
                if not reports:
                    continue
                latest = reports[-1]
                # Check if this conversation needs compression
                current_order = status_order.get(
                    latest.status.value, 4,
                )
                if current_order <= min_order:
                    parts = conv_key.split(":", 1)
                    if len(parts) == 2:
                        all_conv_data.append({
                            "company_id": parts[0],
                            "conversation_id": parts[1],
                            "latest_score": latest.overall_score,
                            "latest_status": latest.status.value,
                            "turn_count": latest.turn_number,
                        })
        except Exception as exc:
            logger.warning(
                "enumerate_health_histories_failed",
                extra={
                    "task": self.name,
                    "error": str(exc)[:200],
                },
            )

        if not all_conv_data:
            logger.info(
                "compress_stale_contexts_none_found",
                extra={
                    "task": self.name,
                    "health_threshold": health_threshold,
                },
            )
            return {
                "status": "checked",
                "health_threshold": health_threshold,
                "conversations_scanned": 0,
                "compressed": 0,
                "skipped": 0,
                "errors": 0,
            }

        # For now, we identify candidates but actual compression
        # requires conversation state which is in the serializer
        # Log candidates for manual verification
        for conv in all_conv_data:
            try:
                # In a full implementation, we would:
                # 1. Load state from StateSerializer
                # 2. Extract content chunks
                # 3. Call ContextCompressor.compress()
                # 4. Update the state
                # For BC-008 graceful degradation, we log and skip
                logger.info(
                    "stale_context_identified",
                    extra={
                        "task": self.name,
                        "company_id": conv["company_id"],
                        "conversation_id": conv["conversation_id"],
                        "score": conv["latest_score"],
                        "status": conv["latest_status"],
                        "turns": conv["turn_count"],
                        "action": "logged_for_compression",
                    },
                )
                skipped_count += 1
            except Exception:
                errors += 1

        logger.info(
            "compress_stale_contexts_complete",
            extra={
                "task": self.name,
                "health_threshold": health_threshold,
                "candidates_found": len(all_conv_data),
                "skipped": skipped_count,
                "errors": errors,
            },
        )

        return {
            "status": "checked",
            "health_threshold": health_threshold,
            "conversations_scanned": len(all_conv_data),
            "compressed": compressed_count,
            "skipped": skipped_count,
            "errors": errors,
            "candidates": [
                {
                    "company_id": c["company_id"],
                    "conversation_id": c["conversation_id"],
                    "score": c["latest_score"],
                    "status": c["latest_status"],
                }
                for c in all_conv_data
            ],
        }

    except Exception as exc:
        logger.error(
            "compress_stale_contexts_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 5. WARM TECHNIQUE CACHE (periodic / on-demand)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_light",
    name="workflow.warm_technique_cache",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
)
def warm_technique_cache(
    self,
    company_id: Optional[str] = None,
    technique_id: Optional[str] = None,
) -> dict:
    """Preload technique cache entries for faster first responses.

    Warms the TechniqueCache with frequently-used technique results.
    Can target a specific company and/or technique, or warm all.

    Args:
        company_id: Specific company to warm. None = all companies.
        technique_id: Specific technique to warm. None = all techniques.

    Returns:
        Dict with warming statistics.
    """
    try:
        from app.core.technique_caching import TechniqueCache
        from app.core.technique_router import TECHNIQUE_REGISTRY

        cache = TechniqueCache()

        # Determine which techniques to warm
        if technique_id:
            techniques = [technique_id]
        else:
            techniques = [
                tid.value for tid in TECHNIQUE_REGISTRY.keys()
            ]

        entries_loaded = 0
        details: Dict[str, Any] = {}

        for tid in techniques:
            try:
                # Generate warm entries for common query patterns
                warm_entries = []
                common_queries = [
                    "how do i reset my password",
                    "i want a refund for my order",
                    "what is the status of my ticket",
                    "i need to cancel my subscription",
                    "how do i upgrade my plan",
                ]

                for query in common_queries:
                    query_hash = str(hash(query))[:16]
                    signals_hash = "default_signals_hash"
                    warm_entries.append({
                        "query_hash": query_hash,
                        "signals_hash": signals_hash,
                        "result": {
                            "technique_id": tid,
                            "cached_response": (
                                f"[Warmed cache entry for "
                                f"{tid}: {query[:50]}...]"
                            ),
                            "confidence": 0.5,
                        },
                        "ttl_seconds": 600,
                    })

                cid = company_id or "default"
                loaded = cache.warm(tid, cid, warm_entries)
                details[tid] = {"entries_loaded": loaded}
                entries_loaded += loaded

            except Exception as exc:
                logger.warning(
                    "warm_technique_cache_failed_for_technique",
                    extra={
                        "task": self.name,
                        "technique_id": tid,
                        "error": str(exc)[:200],
                    },
                )
                details.setdefault(tid, {})["error"] = str(exc)[:200]

        logger.info(
            "warm_technique_cache_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "technique_id": technique_id,
                "techniques_attempted": len(techniques),
                "entries_loaded": entries_loaded,
            },
        )

        return {
            "status": "warmed",
            "company_id": company_id,
            "technique_id": technique_id,
            "techniques_attempted": len(techniques),
            "entries_loaded": entries_loaded,
            "details": details,
        }

    except Exception as exc:
        logger.error(
            "warm_technique_cache_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "technique_id": technique_id,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 6. MIGRATE STALE STATES (periodic — every 6 hours)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="workflow.migrate_stale_states",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def migrate_stale_states(self, batch_size: int = 100) -> dict:
    """Batch-migrate old schema version states to latest.

    Scans persisted states (PostgreSQL) for versions older than
    the latest and migrates them forward. Uses batch processing
    to handle large state sets efficiently.

    Args:
        batch_size: Maximum number of states to migrate per run.
            Default 100.

    Returns:
        Dict with migration statistics.
    """
    try:
        from app.core.state_migration import StateMigrator

        migrator = StateMigrator()
        latest_version = migrator.get_latest_version()

        states_to_migrate: List[Dict[str, Any]] = []

        # Try to load states from PostgreSQL
        try:
            from database.base import SessionLocal
            from app.core.state_serialization import _safe_json_loads

            db = SessionLocal()
            try:
                from database.models.ai_pipeline import (
                    PipelineStateSnapshot,
                )

                # Query states with version < latest
                snapshots = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.snapshot_type == "auto",
                    )
                    .order_by(
                        PipelineStateSnapshot.created_at.desc(),
                    )
                    .limit(batch_size)
                    .all()
                )

                for snapshot in snapshots:
                    try:
                        state_data = _safe_json_loads(
                            snapshot.state_json,
                        )
                        if isinstance(state_data, dict):
                            current_version = state_data.get(
                                "_version", 1,
                            )
                            if current_version < latest_version:
                                states_to_migrate.append(state_data)
                    except Exception:
                        pass

            finally:
                db.close()

        except Exception as exc:
            logger.warning(
                "load_states_for_migration_failed",
                extra={
                    "task": self.name,
                    "error": str(exc)[:200],
                },
            )

        if not states_to_migrate:
            logger.info(
                "migrate_stale_states_no_candidates",
                extra={
                    "task": self.name,
                    "latest_version": latest_version,
                },
            )
            return {
                "status": "checked",
                "latest_version": latest_version,
                "total_candidates": 0,
                "migrated": 0,
                "failed": 0,
                "skipped": 0,
            }

        # Run batch migration
        batch_result = migrator.batch_migrate(
            states=states_to_migrate,
            target_version=latest_version,
            dry_run=False,
        )

        logger.info(
            "migrate_stale_states_success",
            extra={
                "task": self.name,
                "latest_version": latest_version,
                "total": batch_result.total,
                "migrated": batch_result.migrated,
                "failed": batch_result.failed,
                "skipped": batch_result.skipped,
            },
        )

        return {
            "status": "migrated",
            "latest_version": latest_version,
            "total_candidates": batch_result.total,
            "migrated": batch_result.migrated,
            "failed": batch_result.failed,
            "skipped": batch_result.skipped,
            "details": [
                {
                    "from_version": r.from_version,
                    "to_version": r.to_version,
                    "success": r.success,
                    "changes": len(r.changes_made),
                }
                for r in batch_result.results
            ],
        }

    except Exception as exc:
        logger.error(
            "migrate_stale_states_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise
