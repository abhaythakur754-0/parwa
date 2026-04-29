"""
Technique Tasks — Celery tasks for async technique execution and monitoring.

DEP-05: Add technique-related Celery tasks for async technique execution
and monitoring. These tasks will be called by the LangGraph workflow (F-060)
when technique processing needs to happen asynchronously.

BC-001: Every task has company_id as first parameter.
BC-004: All tasks inherit from ParwaBaseTask.
"""

import logging
import time
from typing import Any, Dict, Optional

from app.tasks.base import ParwaBaseTask  # noqa: F401

logger = logging.getLogger("parwa.tasks.technique")


# ── Technique Execution Task ──────────────────────────────────────


class ExecuteTechniqueTask(ParwaBaseTask):
    """Execute a single technique node asynchronously.

    Called by LangGraph workflow (F-060) when a technique needs
    async processing. Records execution metrics in technique_executions table.
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
            # TODO: Full implementation when LangGraph pipeline is built (Week 10)
            # For now, return a stub result with timing
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "technique_executed",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "latency_ms": latency_ms,
                    "model_tier": model_tier,
                },
            )

            return {
                "technique_id": technique_id,
                "status": "stub",
                "latency_ms": latency_ms,
                "tokens_used": 0,
                "message": (
                    f"Technique {technique_id} execution stub — "
                    "full implementation in Week 10+"
                ),
            }

        except Exception as exc:
            logger.error(
                "technique_execution_failed",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
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

        Args:
            company_id: Tenant ID (BC-001).
            execution_data: Dict with all execution metrics.

        Returns:
            True if logged successfully.
        """
        try:
            # TODO: Insert into technique_executions table (Week 10+)
            # when DB session is available in Celery workers
            logger.info(
                "technique_execution_logged",
                extra={
                    "company_id": company_id,
                    "technique_id": execution_data.get("technique_id"),
                    "tokens_overhead": execution_data.get("tokens_overhead", 0),
                    "latency_ms": execution_data.get("latency_ms", 0),
                    "result_status": execution_data.get("result_status", "unknown"),
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
            # TODO: Query technique_executions table, aggregate metrics
            # Full implementation when F-098 is built (Week 16)
            logger.info(
                "technique_metrics_aggregated",
                extra={
                    "company_id": company_id,
                    "window_minutes": window_minutes,
                },
            )

            return {
                "company_id": company_id,
                "window_minutes": window_minutes,
                "status": "stub",
                "message": "Metrics aggregation stub — Week 16",
            }

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

        Args:
            company_id: Tenant ID (BC-001).
            technique_id: The technique to update.
            version: The version label (e.g., "v1", "v2").

        Returns:
            Dict with updated metrics.
        """
        try:
            # TODO: Query technique_executions, compute averages,
            # update technique_versions table
            logger.info(
                "technique_version_metrics_updated",
                extra={
                    "company_id": company_id,
                    "technique_id": technique_id,
                    "version": version,
                },
            )

            return {
                "technique_id": technique_id,
                "version": version,
                "status": "stub",
                "message": "Version metrics update stub — Week 10+",
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
