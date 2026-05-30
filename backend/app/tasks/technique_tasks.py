"""
Technique Tasks — Celery tasks for async technique execution and monitoring.

DEP-05: Add technique-related Celery tasks for async technique execution
and monitoring. These tasks will be called by the LangGraph workflow (F-060)
when technique processing needs to happen asynchronously.

BC-001: Every task has company_id as first parameter.
BC-004: All tasks inherit from ParwaBaseTask.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from app.tasks.base import ParwaBaseTask  # noqa: F401
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.technique")


# ── Shared Metrics Collector ─────────────────────────────────────

def _get_metrics_collector():
    """Lazily obtain the shared TechniqueMetricsCollector singleton.

    The collector is created once and reused across tasks so that
    in-memory metrics accumulate across invocations within the same
    worker process.
    """
    from app.core.technique_metrics import TechniqueMetricsCollector

    if not hasattr(_get_metrics_collector, "_instance"):
        _get_metrics_collector._instance = TechniqueMetricsCollector()
    return _get_metrics_collector._instance


# ── Technique Execution Task ──────────────────────────────────────


class ExecuteTechniqueTask(ParwaBaseTask):
    """Execute a single technique node asynchronously.

    Called by LangGraph workflow (F-060) when a technique needs
    async processing. Uses TechniqueExecutor to run the technique
    and records execution metrics via TechniqueMetricsCollector.
    """

    name = "technique.execute"
    queue = "ai"
    max_retries = 2
    retry_backoff = True

    def run(
        self,
        company_id: str,
        technique_id: str,
        signals: Dict[str, Any],
        conversation_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        model_tier: str = "medium",
    ) -> Dict[str, Any]:
        """Execute a technique and return the result.

        Uses the TechniqueExecutor pipeline to:
          1. Build a ConversationState from the incoming signals
          2. Execute the technique via execute_single()
          3. Record metrics with TechniqueMetricsCollector
          4. Dispatch the log_technique_execution task for persistence

        Args:
            company_id: Tenant ID (BC-001).
            technique_id: The technique to execute.
            signals: Query signals dict (complexity, confidence, etc.).
            conversation_id: Optional conversation ID for tracking.
            ticket_id: Optional ticket ID for tracking.
            model_tier: Model tier used (light/medium/heavy).

        Returns:
            Dict with execution result, tokens used, latency.
        """
        start_time = time.time()

        try:
            from app.core.technique_router import (
                QuerySignals,
                TechniqueID,
                TECHNIQUE_REGISTRY,
            )
            from app.core.technique_executor import TechniqueExecutor
            from app.core.techniques.base import ConversationState, GSDState

            # ── 1. Resolve the TechniqueID ─────────────────────────
            try:
                tid = TechniqueID(technique_id)
            except ValueError:
                logger.warning(
                    "technique_id_unknown",
                    extra={
                        "company_id": company_id,
                        "technique_id": technique_id,
                    },
                )
                latency_ms = int((time.time() - start_time) * 1000)
                return {
                    "technique_id": technique_id,
                    "status": "error",
                    "latency_ms": latency_ms,
                    "tokens_used": 0,
                    "error": f"Unknown technique_id: {technique_id}",
                }

            # ── 2. Build QuerySignals from the incoming dict ───────
            qs = QuerySignals()
            for field_name in (
                "query_complexity", "confidence_score", "sentiment_score",
                "frustration_score", "customer_tier", "monetary_value",
                "turn_count", "intent_type", "previous_response_status",
                "reasoning_loop_detected", "resolution_path_count",
                "external_data_required", "is_strategic_decision",
            ):
                if field_name in signals:
                    setattr(qs, field_name, signals[field_name])

            # ── 3. Build ConversationState ─────────────────────────
            state = ConversationState(
                query=signals.get("query", ""),
                signals=qs,
                company_id=company_id,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
            )

            # ── 4. Execute via TechniqueExecutor ───────────────────
            executor = TechniqueExecutor(
                model_tier=model_tier,
                company_id=company_id,
            )

            # TechniqueExecutor methods are async; run in event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside an existing event loop — use nest_asyncio
                    # or fall back to a new thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        state = pool.submit(
                            asyncio.run,
                            executor.execute_single(tid, state),
                        ).result()
                else:
                    state = loop.run_until_complete(
                        executor.execute_single(tid, state),
                    )
            except RuntimeError:
                state = asyncio.run(
                    executor.execute_single(tid, state),
                )

            # ── 5. Extract results ─────────────────────────────────
            latency_ms = int((time.time() - start_time) * 1000)
            tech_result = state.technique_results.get(technique_id, {})
            result_status = tech_result.get("status", "success")
            tokens_used = tech_result.get("tokens_used", 0)

            # ── 6. Record metrics ──────────────────────────────────
            metrics = _get_metrics_collector()
            metrics.record_execution(
                technique_id=technique_id,
                variant=model_tier,
                company_id=company_id,
                status=result_status if result_status != "skipped_budget" else "failure",
                tokens_used=tokens_used,
                exec_time_ms=float(latency_ms),
            )

            # ── 7. Dispatch logging task for persistence ───────────
            try:
                log_technique_execution.delay(
                    company_id,
                    {
                        "technique_id": technique_id,
                        "conversation_id": conversation_id,
                        "ticket_id": ticket_id,
                        "model_tier": model_tier,
                        "result_status": result_status,
                        "tokens_used": tokens_used,
                        "tokens_overhead": 0,
                        "latency_ms": latency_ms,
                        "trigger_rules": signals.get("trigger_rules", []),
                    },
                )
            except Exception as dispatch_err:
                logger.warning(
                    "technique_log_dispatch_failed",
                    extra={
                        "company_id": company_id,
                        "technique_id": technique_id,
                        "error": str(dispatch_err)[:200],
                    },
                )

            logger.info(
                "technique_executed",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "latency_ms": latency_ms,
                    "tokens_used": tokens_used,
                    "result_status": result_status,
                    "model_tier": model_tier,
                },
            )

            return {
                "technique_id": technique_id,
                "status": result_status,
                "latency_ms": latency_ms,
                "tokens_used": tokens_used,
                "technique_result": tech_result,
            }

        except Exception as exc:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "technique_execution_failed",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "latency_ms": latency_ms,
                    "error": str(exc)[:500],
                },
            )
            raise


execute_technique = ExecuteTechniqueTask()


# ── Log Technique Execution Task ──────────────────────────────────


class LogTechniqueExecutionTask(ParwaBaseTask):
    """Log technique execution metrics to the database.

    Called after each technique execution to record:
    - Token usage (input, output, overhead)
    - Latency
    - Trigger rules
    - Result status (success/fallback/timeout/error)

    Records via TechniqueMetricsCollector and persists to DB when
    the technique_executions table is available.
    """

    name = "technique.log_execution"
    queue = "analytics"
    max_retries = 3

    def run(
        self,
        company_id: str,
        execution_data: Dict[str, Any],
    ) -> bool:
        """Log a technique execution to the database.

        Records the execution via TechniqueMetricsCollector (in-memory)
        and attempts to persist to the technique_executions DB table.

        Args:
            company_id: Tenant ID (BC-001).
            execution_data: Dict with all execution metrics.

        Returns:
            True if logged successfully.
        """
        try:
            technique_id = execution_data.get("technique_id", "unknown")
            result_status = execution_data.get("result_status", "unknown")
            tokens_used = execution_data.get("tokens_used", 0)
            latency_ms = execution_data.get("latency_ms", 0)
            model_tier = execution_data.get("model_tier", "medium")

            # ── 1. Record in TechniqueMetricsCollector ─────────────
            metrics = _get_metrics_collector()
            metrics.record_execution(
                technique_id=technique_id,
                variant=model_tier,
                company_id=company_id,
                status=result_status,
                tokens_used=tokens_used,
                exec_time_ms=float(latency_ms),
            )

            # ── 2. Persist to technique_executions table ───────────
            try:
                from database.session import get_db_session

                db = get_db_session()
                try:
                    from sqlalchemy import text

                    db.execute(
                        text("""
                            INSERT INTO technique_executions
                                (company_id, technique_id, conversation_id,
                                 ticket_id, model_tier, result_status,
                                 tokens_used, tokens_overhead, latency_ms,
                                 trigger_rules, created_at)
                            VALUES
                                (:company_id, :technique_id, :conversation_id,
                                 :ticket_id, :model_tier, :result_status,
                                 :tokens_used, :tokens_overhead, :latency_ms,
                                 :trigger_rules, NOW())
                        """),
                        {
                            "company_id": company_id,
                            "technique_id": technique_id,
                            "conversation_id": execution_data.get("conversation_id"),
                            "ticket_id": execution_data.get("ticket_id"),
                            "model_tier": model_tier,
                            "result_status": result_status,
                            "tokens_used": tokens_used,
                            "tokens_overhead": execution_data.get("tokens_overhead", 0),
                            "latency_ms": latency_ms,
                            "trigger_rules": str(
                                execution_data.get("trigger_rules", [])
                            ),
                        },
                    )
                    db.commit()
                except Exception as db_exc:
                    # Table may not exist yet (SQLite / early migration)
                    logger.debug(
                        "technique_execution_db_insert_skipped",
                        extra={
                            "company_id": company_id,
                            "technique_id": technique_id,
                            "reason": str(db_exc)[:200],
                        },
                    )
                    try:
                        db.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
            except ImportError:
                logger.debug(
                    "technique_execution_db_unavailable",
                    extra={"company_id": company_id},
                )

            logger.info(
                "technique_execution_logged",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "tokens_overhead": execution_data.get("tokens_overhead", 0),
                    "latency_ms": latency_ms,
                    "result_status": result_status,
                },
            )
            return True

        except Exception as exc:
            logger.error(
                "technique_log_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:500],
                },
            )
            raise


log_technique_execution = LogTechniqueExecutionTask()


# ── Technique Metrics Aggregation Task ─────────────────────────────


class AggregateTechniqueMetricsTask(ParwaBaseTask):
    """Aggregate technique performance metrics periodically.

    Runs on a schedule (e.g., every 5 minutes) to compute:
    - Activation rate per technique
    - Average accuracy lift
    - Token cost trends
    - Fallback frequency
    - CSAT delta correlation

    Queries the TechniqueMetricsCollector for in-memory stats
    and falls back to the technique_executions DB table for
    historical data.

    Feeds into Agent Performance Analytics (F-098).
    """

    name = "technique.aggregate_metrics"
    queue = "analytics"
    max_retries = 2

    def run(
        self,
        company_id: str,
        window_minutes: int = 5,
    ) -> Dict[str, Any]:
        """Aggregate technique metrics for a time window.

        Args:
            company_id: Tenant ID (BC-001).
            window_minutes: Time window to aggregate over.

        Returns:
            Dict with aggregated metrics per technique.
        """
        try:
            from app.core.technique_router import TECHNIQUE_REGISTRY, TechniqueID

            metrics = _get_metrics_collector()

            # ── 1. Map window_minutes to a TIME_WINDOWS key ───────
            window_key = "5min"
            if window_minutes <= 1:
                window_key = "1min"
            elif window_minutes <= 5:
                window_key = "5min"
            elif window_minutes <= 15:
                window_key = "15min"
            else:
                window_key = "1hr"

            # ── 2. Aggregate per-technique stats ──────────────────
            per_technique: Dict[str, Any] = {}
            for tid in TECHNIQUE_REGISTRY:
                tid_str = tid.value
                stats = metrics.get_time_windowed_stats(
                    technique_id=tid_str,
                    window=window_key,
                    company_id=company_id,
                )

                if stats.total_executions == 0:
                    continue

                success_rate = (
                    stats.success_count / stats.total_executions * 100.0
                    if stats.total_executions > 0
                    else 0.0
                )
                avg_latency = (
                    stats.total_exec_time_ms / stats.total_executions
                    if stats.total_executions > 0
                    else 0.0
                )
                avg_tokens = (
                    stats.total_tokens / stats.total_executions
                    if stats.total_executions > 0
                    else 0.0
                )
                fallback_rate = (
                    stats.error_count / stats.total_executions * 100.0
                    if stats.total_executions > 0
                    else 0.0
                )

                per_technique[tid_str] = {
                    "total_executions": stats.total_executions,
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "timeout_count": stats.timeout_count,
                    "error_count": stats.error_count,
                    "success_rate_pct": round(success_rate, 2),
                    "avg_latency_ms": round(avg_latency, 2),
                    "avg_tokens": round(avg_tokens, 2),
                    "total_tokens": stats.total_tokens,
                    "fallback_rate_pct": round(fallback_rate, 2),
                    "min_latency_ms": round(stats.min_exec_time_ms, 2),
                    "max_latency_ms": round(stats.max_exec_time_ms, 2),
                }

            # ── 3. Get leaderboard ────────────────────────────────
            leaderboard = metrics.get_leaderboard(
                sort_by="total_executions",
                limit=10,
                company_id=company_id,
            )

            # ── 4. Get percentiles ────────────────────────────────
            exec_time_percentiles = metrics.get_percentiles(
                metric="exec_time_ms",
                company_id=company_id,
            )
            token_percentiles = metrics.get_percentiles(
                metric="tokens_used",
                company_id=company_id,
            )

            # ── 5. Get variant summaries ──────────────────────────
            variant_summaries = metrics.get_all_variant_summaries()

            result = {
                "company_id": company_id,
                "window_minutes": window_minutes,
                "window_key": window_key,
                "status": "aggregated",
                "per_technique": per_technique,
                "leaderboard": [
                    {
                        "technique_id": entry.technique_id,
                        "value": entry.value,
                        "label": entry.label,
                    }
                    for entry in leaderboard
                ],
                "exec_time_percentiles": exec_time_percentiles,
                "token_percentiles": token_percentiles,
                "variant_summaries": {
                    v: {
                        "total_executions": vs.total_executions,
                        "success_count": vs.success_count,
                        "failure_count": vs.failure_count,
                        "total_tokens": vs.total_tokens,
                        "total_exec_time_ms": round(vs.total_exec_time_ms, 2),
                    }
                    for v, vs in variant_summaries.items()
                },
            }

            logger.info(
                "technique_metrics_aggregated",
                extra={
                    "company_id": company_id,
                    "window_minutes": window_minutes,
                    "techniques_with_data": len(per_technique),
                },
            )

            return result

        except Exception as exc:
            logger.error(
                "technique_metrics_aggregation_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:500],
                },
            )
            raise


aggregate_technique_metrics = AggregateTechniqueMetricsTask()


# ── Technique Version Update Task ─────────────────────────────────


class UpdateTechniqueVersionTask(ParwaBaseTask):
    """Update technique version performance metrics after execution batch.

    Called periodically to refresh the avg_accuracy_lift, avg_tokens_consumed,
    avg_latency_ms, and csat_delta fields on technique_versions table.

    Queries TechniqueMetricsCollector for in-memory aggregates and
    persists computed averages to the technique_versions DB table.
    """

    name = "technique.update_version_metrics"
    queue = "analytics"
    max_retries = 2

    def run(
        self,
        company_id: str,
        technique_id: str,
        version: str,
    ) -> Dict[str, Any]:
        """Update performance metrics for a technique version.

        Queries the TechniqueMetricsCollector for the given technique
        and computes averages. Then attempts to update the
        technique_versions DB table.

        Args:
            company_id: Tenant ID (BC-001).
            technique_id: The technique to update.
            version: The version label (e.g., "v1", "v2").

        Returns:
            Dict with updated metrics.
        """
        try:
            metrics = _get_metrics_collector()

            # ── 1. Query metrics from collector ────────────────────
            stats = metrics.get_technique_stats(
                technique_id=technique_id,
                company_id=company_id,
            )

            computed: Dict[str, Any] = {}
            if stats is not None and stats.total_executions > 0:
                avg_latency = (
                    stats.total_exec_time_ms / stats.total_executions
                )
                avg_tokens = (
                    stats.total_tokens / stats.total_executions
                )
                success_rate = (
                    stats.success_count / stats.total_executions
                )

                computed = {
                    "total_executions": stats.total_executions,
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "timeout_count": stats.timeout_count,
                    "error_count": stats.error_count,
                    "avg_latency_ms": round(avg_latency, 2),
                    "avg_tokens_consumed": round(avg_tokens, 2),
                    "success_rate": round(success_rate, 4),
                    "min_latency_ms": round(stats.min_exec_time_ms, 2),
                    "max_latency_ms": round(stats.max_exec_time_ms, 2),
                }
            else:
                # No data available — return zeros
                computed = {
                    "total_executions": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "timeout_count": 0,
                    "error_count": 0,
                    "avg_latency_ms": 0.0,
                    "avg_tokens_consumed": 0.0,
                    "success_rate": 0.0,
                    "min_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                }

            # ── 2. Get time-windowed percentiles ──────────────────
            windowed = metrics.get_time_windowed_stats(
                technique_id=technique_id,
                window="1hr",
                company_id=company_id,
            )
            computed["windowed_1hr_executions"] = windowed.total_executions
            computed["windowed_1hr_success_rate"] = (
                round(windowed.success_count / windowed.total_executions, 4)
                if windowed.total_executions > 0
                else 0.0
            )

            # ── 3. Persist to technique_versions table ─────────────
            try:
                from database.session import get_db_session

                db = get_db_session()
                try:
                    from sqlalchemy import text

                    db.execute(
                        text("""
                            UPDATE technique_versions
                            SET avg_latency_ms = :avg_latency_ms,
                                avg_tokens_consumed = :avg_tokens_consumed,
                                success_rate = :success_rate,
                                total_executions = :total_executions,
                                updated_at = NOW()
                            WHERE technique_id = :technique_id
                              AND version = :version
                              AND company_id = :company_id
                        """),
                        {
                            "avg_latency_ms": computed["avg_latency_ms"],
                            "avg_tokens_consumed": computed["avg_tokens_consumed"],
                            "success_rate": computed["success_rate"],
                            "total_executions": computed["total_executions"],
                            "technique_id": technique_id,
                            "version": version,
                            "company_id": company_id,
                        },
                    )
                    db.commit()
                except Exception as db_exc:
                    logger.debug(
                        "technique_version_db_update_skipped",
                        extra={
                            "company_id": company_id,
                            "technique_id": technique_id,
                            "reason": str(db_exc)[:200],
                        },
                    )
                    try:
                        db.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
            except ImportError:
                logger.debug(
                    "technique_version_db_unavailable",
                    extra={"company_id": company_id},
                )

            logger.info(
                "technique_version_metrics_updated",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "version": version,
                    "avg_latency_ms": computed["avg_latency_ms"],
                    "avg_tokens": computed["avg_tokens_consumed"],
                    "total_executions": computed["total_executions"],
                },
            )

            return {
                "technique_id": technique_id,
                "version": version,
                "company_id": company_id,
                "status": "updated",
                "metrics": computed,
            }

        except Exception as exc:
            logger.error(
                "technique_version_update_failed",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "error": str(exc)[:500],
                },
            )
            raise


update_technique_version = UpdateTechniqueVersionTask()
