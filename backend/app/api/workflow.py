"""
PARWA Workflow API Router (Week 10 Day 4)

REST endpoints for the AI Core State Engine + Workflow pipeline.
Wires together the 16 core modules built in Days 1-3:

  - GSDEngine: GSD state machine for multi-step conversations
  - LangGraphWorkflow: Orchestration pipeline
  - StateSerializer: Redis/PostgreSQL state persistence
  - ContextHealthMeter: Context quality monitoring
  - ContextCompressor: Token-aware context compression
  - TechniqueMetricsCollector: Technique execution metrics
  - TechniqueCache: LRU cache with TTL
  - CapacityMonitor: Concurrent execution tracking
  - TenantConfigManager: Per-tenant configuration
  - StateMigrator: Schema version migration
  - TechniqueRouter: Technique selection and routing
  - SharedGSDManager: Cross-ticket GSD analytics
  - DSPyIntegration: DSPy framework bridge

Building Codes:
  - BC-001: Multi-Tenant Isolation (company_id scoping)
  - BC-004: Background Jobs (Celery dispatch patterns)
  - BC-008: Graceful degradation (never crash)
  - BC-011: JWT authentication via dependency injection
  - BC-012: Structured JSON responses with UTC timestamps

Import patterns:
  - Lazy service/core imports inside endpoint functions to avoid
    circular imports and startup overhead.
  - Dependencies: require_roles, get_company_id, get_current_user, get_db.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    require_roles,
    get_company_id,
    get_current_user,
)
from app.api.schemas.workflow import (
    CapacityConfigureRequest,
    CapacityConfigureResponse,
    CapacityStatusResponse,
    CapacityVariantStatus,
    ContextCompressRequest,
    ContextCompressResponse,
    ContextHealthResponse,
    GSDAnalyticsResponse,
    GSDTransitionsResponse,
    HealthAlertSchema,
    HealthMetricsSchema,
    HealthStatus,
    LeaderboardEntrySchema,
    LeaderboardResponse,
    MetricsResponse,
    StateMigrateRequest,
    StateMigrateResponse,
    StateTransitionRequest,
    StateTransitionResponse,
    TechniqueStatsSchema,
    TenantConfigResponse,
    TenantConfigUpdateRequest,
    TenantConfigUpdateResponse,
    VariantMetricsResponse,
    VariantSummarySchema,
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowStateResponse,
)
from app.exceptions import NotFoundError, ValidationError
from database.base import get_db
from database.models.core import User

router = APIRouter(
    prefix="/api/v1/workflow",
    tags=["workflow"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ═══════════════════════════════════════════════════════════════════
# 1. WORKFLOW EXECUTION
# ═══════════════════════════════════════════════════════════════════


@router.post("/execute", response_model=WorkflowExecuteResponse)
def execute_workflow(
    body: WorkflowExecuteRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin", "agent")),
) -> WorkflowExecuteResponse:
    """Execute a full workflow pipeline (GSD → technique → response).

    Runs the LangGraph workflow for a customer query, performing:
    1. GSD state determination
    2. Technique routing based on intent/signals
    3. Response generation via the selected technique
    4. State persistence via StateSerializer
    """
    import time

    try:
        from app.core.langgraph_workflow import LangGraphWorkflow
        from app.core.technique_router import QuerySignals
        from app.core.techniques.base import ConversationState, GSDState

        start = time.monotonic()

        # Build initial conversation state
        signals = QuerySignals(
            intent_type=body.context.get("intent_type", "general"),
            sentiment_score=body.context.get("sentiment_score", 0.0),
            confidence_score=body.context.get("confidence_score", 0.5),
            urgency_level=body.context.get("urgency_level", "medium"),
            customer_tier=body.customer_tier,
            language_code=body.context.get("language_code", "en"),
        )

        state = ConversationState(
            query=body.query,
            signals=signals,
            gsd_state=GSDState.NEW,
            ticket_id=body.ticket_id,
            conversation_id=body.conversation_id,
            company_id=company_id,
        )

        # Execute workflow
        workflow = LangGraphWorkflow()
        result_state = workflow.execute(state)

        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        gsd_val = (
            result_state.gsd_state.value
            if hasattr(result_state.gsd_state, "value")
            else str(result_state.gsd_state)
        )

        return WorkflowExecuteResponse(
            status="ok",
            conversation_id=body.conversation_id,
            ticket_id=body.ticket_id,
            gsd_state=gsd_val,
            technique_used=(
                result_state.technique_results.get("technique_id")
                if result_state.technique_results
                else None
            ),
            response=result_state.final_response,
            token_usage=result_state.token_usage,
            execution_time_ms=elapsed_ms,
            metadata={
                "variant": body.context.get("variant", "parwa"),
                "channel": body.channel,
            },
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "workflow_execute_failed",
            extra={
                "company_id": company_id,
                "conversation_id": body.conversation_id,
                "error": str(exc)[:500],
            },
        )

        return WorkflowExecuteResponse(
            status="error",
            conversation_id=body.conversation_id,
            ticket_id=body.ticket_id,
            gsd_state="new",
            response=None,
            token_usage=0,
            execution_time_ms=0.0,
            metadata={"error": str(exc)[:500]},
        )


# ═══════════════════════════════════════════════════════════════════
# 2. WORKFLOW STATE
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/state/{conversation_id}",
    response_model=WorkflowStateResponse,
)
def get_workflow_state(
    conversation_id: str,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkflowStateResponse:
    """Get the current workflow state for a conversation.

    Loads the serialized ConversationState from Redis/PostgreSQL
    and returns a summary including GSD state, technique results,
    and available transitions.
    """
    try:
        from app.core.state_serialization import StateSerializer

        serializer = StateSerializer()

        # Look up by conversation_id — try finding via ticket
        # StateSerializer uses ticket_id as primary key, so we
        # attempt to load by conversation_id as ticket_id fallback
        state = serializer.load_state(
            ticket_id=conversation_id,
            company_id=company_id,
        )

        if state is None:
            raise NotFoundError(
                message=(
                    f"No workflow state found for "
                    f"conversation '{conversation_id}'"
                ),
                details={"conversation_id": conversation_id},
            )

        gsd_val = (
            state.gsd_state.value
            if hasattr(state.gsd_state, "value")
            else str(state.gsd_state)
        )

        # Get available transitions
        available = []
        try:
            from app.core.gsd_engine import GSDEngine

            engine = GSDEngine()
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Use nest_asyncio or create new loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    futures = []
                    futures.append(
                        pool.submit(
                            asyncio.run,
                            engine.get_available_transitions(
                                state.gsd_state,
                                engine.get_variant(company_id),
                            ),
                        )
                    )
                    results = [f.result() for f in futures]
                    transitions = results[0]
            else:
                transitions = loop.run_until_complete(
                    engine.get_available_transitions(
                        state.gsd_state,
                        engine.get_variant(company_id),
                    )
                )

            available = [
                t.value if hasattr(t, "value") else str(t)
                for t in transitions
            ]
        except Exception:
            available = []

        # Check terminal state
        is_terminal = gsd_val in ("closed", "human_handoff")

        # Serialize history
        history = []
        if state.gsd_history:
            for h in state.gsd_history:
                history.append(
                    {
                        "state": (
                            h.value if hasattr(h, "value") else str(h)
                        ),
                    }
                )

        return WorkflowStateResponse(
            status="ok",
            conversation_id=conversation_id,
            ticket_id=state.ticket_id,
            company_id=state.company_id,
            gsd_state=gsd_val,
            gsd_history=history,
            technique_results=state.technique_results or {},
            token_usage=state.token_usage,
            is_terminal=is_terminal,
            available_transitions=available,
        )

    except NotFoundError:
        raise
    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_workflow_state_failed",
            extra={
                "company_id": company_id,
                "conversation_id": conversation_id,
                "error": str(exc)[:500],
            },
        )
        raise


@router.post(
    "/state/{conversation_id}/transition",
    response_model=StateTransitionResponse,
)
def force_state_transition(
    conversation_id: str,
    body: StateTransitionRequest,
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
) -> StateTransitionResponse:
    """Force a GSD state transition.

    Bypasses normal AI-driven state determination to manually
    set the GSD state. Useful for admin overrides, testing,
    and recovery scenarios.
    """
    try:
        from app.core.state_serialization import StateSerializer
        from app.core.gsd_engine import GSDEngine
        from app.core.techniques.base import GSDState

        serializer = StateSerializer()
        engine = GSDEngine()

        # Load current state
        state = serializer.load_state(
            ticket_id=conversation_id,
            company_id=company_id,
        )

        if state is None:
            raise NotFoundError(
                message=(
                    f"No workflow state found for "
                    f"conversation '{conversation_id}'"
                ),
                details={"conversation_id": conversation_id},
            )

        previous_state = (
            state.gsd_state.value
            if hasattr(state.gsd_state, "value")
            else str(state.gsd_state)
        )

        # Execute transition
        import asyncio

        target = GSDState(body.target_state.value)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        engine.transition(
                            state,
                            target,
                            trigger_reason=body.trigger_reason,
                            metadata=body.metadata,
                        ),
                    )
                    updated_state = future.result()
            else:
                updated_state = loop.run_until_complete(
                    engine.transition(
                        state,
                        target,
                        trigger_reason=body.trigger_reason,
                        metadata=body.metadata,
                    )
                )
        except Exception as transition_exc:
            raise ValidationError(
                message=f"Transition failed: {transition_exc}",
                details={
                    "from_state": previous_state,
                    "to_state": body.target_state.value,
                    "error": str(transition_exc)[:300],
                },
            )

        # Persist updated state
        import asyncio as aio

        try:
            serializer.save_state(
                ticket_id=conversation_id,
                company_id=company_id,
                conversation_state=updated_state,
                snapshot_type="manual",
            )
        except Exception:
            # BC-008: Graceful degradation on save failure
            from app.logger import get_logger

            logger = get_logger("workflow_api")
            logger.warning(
                "state_persist_failed_after_transition",
                extra={
                    "conversation_id": conversation_id,
                    "error": "State updated in memory but not persisted",
                },
            )

        new_state = (
            updated_state.gsd_state.value
            if hasattr(updated_state.gsd_state, "value")
            else str(updated_state.gsd_state)
        )

        return StateTransitionResponse(
            status="ok",
            previous_state=previous_state,
            current_state=new_state,
            trigger_reason=body.trigger_reason,
            is_terminal=new_state in ("closed", "human_handoff"),
        )

    except (NotFoundError, ValidationError):
        raise
    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "force_transition_failed",
            extra={
                "company_id": company_id,
                "conversation_id": conversation_id,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 3. CONTEXT HEALTH
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/context/health/{conversation_id}",
    response_model=ContextHealthResponse,
)
def get_context_health(
    conversation_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> ContextHealthResponse:
    """Get context health meter status for a conversation.

    Returns the most recent health report including overall score,
    per-metric measurements, active alerts, and recommendations.
    """
    try:
        from app.core.context_health import (
            ContextHealthMeter,
            HealthMetrics,
        )

        meter = ContextHealthMeter()
        report = meter.get_latest_report(company_id, conversation_id)

        if report is None:
            return ContextHealthResponse(
                status="ok",
                conversation_id=conversation_id,
                company_id=company_id,
                overall_score=1.0,
                health_status=HealthStatus.HEALTHY,
                metrics=HealthMetricsSchema(),
                alerts=[],
                turn_number=0,
                timestamp="",
                recommendations=[
                    "No health data available yet for this conversation",
                ],
            )

        # Map alerts
        alert_schemas = []
        for a in report.alerts:
            alert_schemas.append(
                HealthAlertSchema(
                    alert_type=a.alert_type.value,
                    severity=HealthStatus(a.severity.value),
                    message=a.message,
                    metric_name=a.metric_name,
                    metric_value=a.metric_value,
                    threshold=a.threshold,
                    timestamp=a.timestamp,
                )
            )

        return ContextHealthResponse(
            status="ok",
            conversation_id=conversation_id,
            company_id=report.company_id or company_id,
            overall_score=report.overall_score,
            health_status=HealthStatus(report.status.value),
            metrics=HealthMetricsSchema(
                token_usage_ratio=report.metrics.token_usage_ratio,
                compression_ratio=report.metrics.compression_ratio,
                relevance_score=report.metrics.relevance_score,
                freshness_score=report.metrics.freshness_score,
                signal_preservation=report.metrics.signal_preservation,
                context_coherence=report.metrics.context_coherence,
            ),
            alerts=alert_schemas,
            turn_number=report.turn_number,
            timestamp=report.timestamp,
            recommendations=report.recommendations,
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "context_health_check_failed",
            extra={
                "company_id": company_id,
                "conversation_id": conversation_id,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 4. CONTEXT COMPRESSION
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/context/compress",
    response_model=ContextCompressResponse,
)
def compress_context(
    body: ContextCompressRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> ContextCompressResponse:
    """Trigger context compression for a conversation.

    Compresses the provided content chunks using the specified
    strategy to fit within the token budget.
    """
    try:
        from app.core.context_compression import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            content=body.content,
            token_counts=body.token_counts or [],
            priorities=body.priorities or [],
        )

        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        compressor.compress(company_id, input_data),
                    )
                    output = future.result()
            else:
                output = loop.run_until_complete(
                    compressor.compress(company_id, input_data)
                )
        except Exception:
            output = asyncio.run(
                compressor.compress(company_id, input_data)
            )

        return ContextCompressResponse(
            status="ok",
            conversation_id=body.conversation_id,
            original_token_count=output.original_token_count,
            compressed_token_count=output.compressed_token_count,
            compression_ratio=output.compression_ratio,
            strategy_used=output.strategy_used,
            chunks_removed=output.chunks_removed,
            chunks_retained=output.chunks_retained,
            processing_time_ms=output.processing_time_ms,
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "context_compress_failed",
            extra={
                "company_id": company_id,
                "conversation_id": body.conversation_id,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 5. TECHNIQUE METRICS
# ═══════════════════════════════════════════════════════════════════


@router.get("/metrics", response_model=MetricsResponse)
def get_technique_metrics(
    company_id: str = Depends(get_company_id),
    technique_id: Optional[str] = Query(None),
    window: Optional[str] = Query(
        None,
        description="Time window: 1min, 5min, 15min, 1hr",
    ),
    user: User = Depends(require_roles("owner", "admin")),
) -> MetricsResponse:
    """Get technique execution metrics.

    Returns aggregated execution statistics per technique including
    success rates, token usage, and timing percentiles.
    Supports time-windowed filtering.
    """
    try:
        from app.core.technique_metrics import TechniqueMetricsCollector

        collector = TechniqueMetricsCollector()

        # Get all technique IDs
        technique_ids = []
        if technique_id:
            technique_ids = [technique_id]
        else:
            # Get all unique technique IDs from stats
            for (tid, _) in collector._stats.keys():
                if tid not in technique_ids:
                    technique_ids.append(tid)

        technique_schemas = []
        total_exec = 0
        total_tokens = 0

        for tid in technique_ids:
            if window:
                stats = collector.get_time_windowed_stats(
                    technique_id=tid,
                    window=window,
                    company_id=company_id,
                )
            else:
                stats = collector.get_technique_stats(
                    technique_id=tid,
                    company_id=company_id,
                )

            if stats is None:
                continue

            success_rate = (
                (stats.success_count / stats.total_executions * 100)
                if stats.total_executions > 0
                else 0.0
            )
            avg_time = (
                stats.total_exec_time_ms / stats.total_executions
                if stats.total_executions > 0
                else 0.0
            )
            min_time = (
                stats.min_exec_time_ms
                if stats.min_exec_time_ms != float("inf")
                else 0.0
            )

            technique_schemas.append(
                TechniqueStatsSchema(
                    technique_id=stats.technique_id,
                    total_executions=stats.total_executions,
                    success_count=stats.success_count,
                    failure_count=stats.failure_count,
                    timeout_count=stats.timeout_count,
                    error_count=stats.error_count,
                    total_tokens=stats.total_tokens,
                    avg_exec_time_ms=round(avg_time, 2),
                    min_exec_time_ms=round(min_time, 2),
                    max_exec_time_ms=round(stats.max_exec_time_ms, 2),
                    success_rate=round(success_rate, 2),
                )
            )
            total_exec += stats.total_executions
            total_tokens += stats.total_tokens

        # Percentiles
        percentiles = collector.get_percentiles(
            metric="exec_time_ms",
            company_id=company_id,
        )

        return MetricsResponse(
            status="ok",
            techniques=technique_schemas,
            total_executions=total_exec,
            total_tokens=total_tokens,
            window=window,
            percentiles=percentiles,
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_metrics_failed",
            extra={
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        raise


@router.get("/metrics/leaderboard", response_model=LeaderboardResponse)
def get_technique_leaderboard(
    company_id: str = Depends(get_company_id),
    sort_by: str = Query(
        "total_executions",
        description=(
            "Sort metric: total_executions, success_rate, "
            "avg_exec_time_ms, total_tokens, avg_tokens, "
            "failure_rate"
        ),
    ),
    limit: int = Query(10, ge=1, le=50, description="Max entries"),
    user: User = Depends(get_current_user),
) -> LeaderboardResponse:
    """Get technique leaderboard.

    Returns techniques ranked by the specified metric. Useful for
    identifying top performers and bottlenecks.
    """
    try:
        from app.core.technique_metrics import TechniqueMetricsCollector

        collector = TechniqueMetricsCollector()
        entries = collector.get_leaderboard(
            sort_by=sort_by,
            limit=limit,
            company_id=company_id,
        )

        return LeaderboardResponse(
            status="ok",
            sort_by=sort_by,
            entries=[
                LeaderboardEntrySchema(
                    rank=i + 1,
                    technique_id=e.technique_id,
                    value=e.value,
                    label=e.label,
                )
                for i, e in enumerate(entries)
            ],
            total_techniques=len(entries),
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_leaderboard_failed",
            extra={
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        raise


@router.get(
    "/metrics/variants",
    response_model=VariantMetricsResponse,
)
def get_variant_metrics(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> VariantMetricsResponse:
    """Get per-variant execution summaries.

    Returns aggregated metrics for each variant (mini_parwa, parwa,
    high_parwa) including execution counts, success rates, and
    per-technique breakdowns.
    """
    try:
        from app.core.technique_metrics import TechniqueMetricsCollector

        collector = TechniqueMetricsCollector()
        all_summaries = collector.get_all_variant_summaries()

        variant_schemas = []
        for variant, summary in all_summaries.items():
            success_rate = (
                (summary.success_count / summary.total_executions * 100)
                if summary.total_executions > 0
                else 0.0
            )
            variant_schemas.append(
                VariantSummarySchema(
                    variant=summary.variant,
                    total_executions=summary.total_executions,
                    success_count=summary.success_count,
                    failure_count=summary.failure_count,
                    total_tokens=summary.total_tokens,
                    total_exec_time_ms=summary.total_exec_time_ms,
                    success_rate=round(success_rate, 2),
                    technique_counts=summary.technique_counts,
                )
            )

        return VariantMetricsResponse(
            status="ok",
            variants=variant_schemas,
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_variant_metrics_failed",
            extra={
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 6. CAPACITY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/capacity/{company_id}",
    response_model=CapacityStatusResponse,
)
def get_capacity_status(
    company_id: str,
    user: User = Depends(get_current_user),
) -> CapacityStatusResponse:
    """Get capacity status for a company.

    Returns current utilization per variant, queue sizes,
    active alerts, and auto-scaling suggestions.
    """
    try:
        from app.core.capacity_monitor import CapacityMonitor

        monitor = CapacityMonitor()
        overflow = monitor.get_overflow_status(company_id)

        variant_statuses = []
        for variant, vstatus in overflow["variants"].items():
            variant_statuses.append(
                CapacityVariantStatus(
                    variant=variant,
                    used=vstatus["max_concurrent"]
                    - (
                        vstatus["max_concurrent"]
                        * vstatus["utilization_percentage"]
                        // 100
                    )
                    if vstatus["utilization_percentage"] > 0
                    else 0,
                    total=vstatus["max_concurrent"],
                    available=max(
                        0,
                        vstatus["max_concurrent"]
                        - int(
                            vstatus["max_concurrent"]
                            * vstatus["utilization_percentage"]
                            / 100
                        ),
                    ),
                    percentage=vstatus["utilization_percentage"],
                    queue_size=vstatus["queue_size"],
                )
            )

        alerts = monitor.get_alerts(company_id)

        return CapacityStatusResponse(
            status="ok",
            company_id=company_id,
            variants=variant_statuses,
            has_overflow=overflow["has_overflow"],
            total_queued=overflow["total_queued"],
            alerts=alerts,
            scaling_suggestion=overflow.get("scaling_suggestion"),
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_capacity_status_failed",
            extra={
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        raise


@router.post(
    "/capacity/{company_id}/configure",
    response_model=CapacityConfigureResponse,
)
def configure_capacity(
    company_id: str,
    body: CapacityConfigureRequest,
    user: User = Depends(require_roles("owner", "admin")),
) -> CapacityConfigureResponse:
    """Configure capacity limits for a company.

    Sets custom max_concurrent limits for a specific variant.
    Raises ValidationError if limit would be exceeded by active slots.
    """
    try:
        from app.core.capacity_monitor import CapacityMonitor

        monitor = CapacityMonitor()
        monitor.configure_limits(
            company_id=company_id,
            variant=body.variant,
            max_concurrent=body.max_concurrent,
        )

        return CapacityConfigureResponse(
            status="ok",
            company_id=company_id,
            variant=body.variant,
            max_concurrent=body.max_concurrent,
        )

    except ValueError as exc:
        raise ValidationError(
            message=str(exc),
            details={"variant": body.variant, "max_concurrent": body.max_concurrent},
        )
    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "configure_capacity_failed",
            extra={
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 7. TENANT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/config/{company_id}",
    response_model=TenantConfigResponse,
)
def get_tenant_config(
    company_id: str,
    user: User = Depends(get_current_user),
) -> TenantConfigResponse:
    """Get tenant configuration.

    Returns the full merged configuration (variant defaults +
    per-company overrides) for all categories.
    """
    try:
        from app.core.per_tenant_config import TenantConfigManager
        from dataclasses import asdict

        manager = TenantConfigManager()
        config = manager.get_config(company_id)

        config_dict = asdict(config)
        version = manager._versions.get(company_id, 0)
        variant = manager._tenant_variants.get(
            company_id, manager._default_variant,
        )

        return TenantConfigResponse(
            status="ok",
            company_id=company_id,
            config=config_dict,
            version=version,
            variant_type=variant,
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_tenant_config_failed",
            extra={
                "company_id": company_id,
                "error": str(exc)[:500],
            },
        )
        raise


@router.put(
    "/config/{company_id}/{category}",
    response_model=TenantConfigUpdateResponse,
)
def update_tenant_config(
    company_id: str,
    category: str,
    body: TenantConfigUpdateRequest,
    user: User = Depends(require_roles("owner", "admin")),
) -> TenantConfigUpdateResponse:
    """Update tenant configuration for a specific category.

    Categories: technique, compression, workflow, model.
    Only provided fields will be updated; others remain unchanged.
    """
    valid_categories = {"technique", "compression", "workflow", "model"}

    if category not in valid_categories:
        raise ValidationError(
            message=f"Invalid category: {category}",
            details={
                "valid_categories": sorted(valid_categories),
            },
        )

    try:
        from app.core.per_tenant_config import TenantConfigManager
        from dataclasses import asdict

        manager = TenantConfigManager()
        updated = manager.update_config(
            company_id=company_id,
            category=category,
            config_dict=body.config,
        )

        version = manager._versions.get(company_id, 0)

        # Extract only the updated category for response
        category_config = asdict(updated)
        for cat in valid_categories:
            if cat != category:
                category_config.pop(cat, None)

        return TenantConfigUpdateResponse(
            status="ok",
            company_id=company_id,
            category=category,
            version=version,
            updated_config=category_config,
        )

    except ValueError as exc:
        raise ValidationError(
            message=str(exc),
            details={"category": category},
        )
    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "update_tenant_config_failed",
            extra={
                "company_id": company_id,
                "category": category,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 8. GSD TRANSITIONS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/gsd/{company_id}/{ticket_id}/transitions",
    response_model=GSDTransitionsResponse,
)
def get_gsd_transitions(
    company_id: str,
    ticket_id: str,
    user: User = Depends(get_current_user),
) -> GSDTransitionsResponse:
    """Get GSD transition history for a ticket.

    Returns the ordered list of all GSD state transitions
    recorded during the conversation.
    """
    try:
        from app.core.state_serialization import StateSerializer
        from app.core.gsd_engine import GSDEngine
        from app.core.shared_gsd import SharedGSDManager

        serializer = StateSerializer()
        state = serializer.load_state(
            ticket_id=ticket_id,
            company_id=company_id,
        )

        if state is None:
            raise NotFoundError(
                message=(
                    f"No workflow state found for ticket '{ticket_id}'"
                ),
                details={"ticket_id": ticket_id},
            )

        # Try SharedGSDManager for transition history
        transitions = []
        try:
            gsd_manager = SharedGSDManager()
            history = gsd_manager.get_transition_history(
                company_id, ticket_id,
            )
            if history:
                for record in history:
                    transitions.append(
                        {
                            "state": record.get("state", "unknown"),
                            "timestamp": record.get("timestamp", ""),
                            "trigger": record.get("trigger", ""),
                            "metadata": record.get("metadata", {}),
                        }
                    )
        except Exception:
            # Fallback to gsd_history on the state
            if state.gsd_history:
                for h in state.gsd_history:
                    transitions.append(
                        {
                            "state": (
                                h.value if hasattr(h, "value")
                                else str(h)
                            ),
                            "timestamp": "",
                            "trigger": "",
                            "metadata": {},
                        }
                    )

        return GSDTransitionsResponse(
            status="ok",
            company_id=company_id,
            ticket_id=ticket_id,
            transitions=transitions,
            total_transitions=len(transitions),
        )

    except NotFoundError:
        raise
    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_gsd_transitions_failed",
            extra={
                "company_id": company_id,
                "ticket_id": ticket_id,
                "error": str(exc)[:500],
            },
        )
        raise


@router.get(
    "/gsd/{company_id}/{ticket_id}/analytics",
    response_model=GSDAnalyticsResponse,
)
def get_gsd_analytics(
    company_id: str,
    ticket_id: str,
    user: User = Depends(get_current_user),
) -> GSDAnalyticsResponse:
    """Get GSD analytics for a ticket.

    Provides transition reasoning, signal snapshots, loop counts,
    resolution time estimates, and state distribution analytics.
    """
    try:
        from app.core.state_serialization import StateSerializer
        from app.core.gsd_engine import GSDEngine

        serializer = StateSerializer()
        state = serializer.load_state(
            ticket_id=ticket_id,
            company_id=company_id,
        )

        if state is None:
            raise NotFoundError(
                message=(
                    f"No workflow state found for ticket '{ticket_id}'"
                ),
                details={"ticket_id": ticket_id},
            )

        engine = GSDEngine()

        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    futures = [
                        pool.submit(
                            asyncio.run,
                            engine.get_transition_reason(state),
                        ),
                        pool.submit(
                            asyncio.run,
                            engine.get_conversation_summary(state),
                        ),
                    ]
                    reason = futures[0].result()
                    summary = futures[1].result()
            else:
                reason = loop.run_until_complete(
                    engine.get_transition_reason(state)
                )
                summary = loop.run_until_complete(
                    engine.get_conversation_summary(state)
                )
        except Exception:
            reason = {
                "current_state": "unknown",
                "recommended_next_state": "unknown",
                "reasoning_chain": [],
                "signals_snapshot": {},
            }
            summary = {}

        return GSDAnalyticsResponse(
            status="ok",
            company_id=company_id,
            ticket_id=ticket_id,
            current_state=reason.get("current_state", "unknown"),
            recommended_next_state=reason.get(
                "recommended_next_state", "unknown",
            ),
            variant=reason.get("variant", "parwa"),
            reasoning_chain=reason.get("reasoning_chain", []),
            signals_snapshot=reason.get("signals_snapshot", {}),
            escalation_conditions_met=reason.get(
                "escalation_conditions_met", False,
            ),
            diagnosis_loop_count=reason.get("diagnosis_loops", 0),
            time_in_current_state_seconds=summary.get(
                "time_in_current_state_seconds", 0.0,
            ),
            estimated_resolution_time_minutes=summary.get(
                "estimated_resolution_time_minutes", 0,
            ),
            state_distribution=summary.get("state_distribution", {}),
        )

    except NotFoundError:
        raise
    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "get_gsd_analytics_failed",
            extra={
                "company_id": company_id,
                "ticket_id": ticket_id,
                "error": str(exc)[:500],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════
# 9. STATE MIGRATION
# ═══════════════════════════════════════════════════════════════════


@router.post("/migrate", response_model=StateMigrateResponse)
def migrate_state(
    body: StateMigrateRequest,
    user: User = Depends(require_roles("owner", "admin")),
) -> StateMigrateResponse:
    """Migrate a state to the latest schema version.

    Applies forward migrations to bring a state dict up to the
    latest version. Supports dry-run mode for previewing changes.
    """
    try:
        from app.core.state_migration import StateMigrator

        migrator = StateMigrator()
        result = migrator.migrate_state(
            state_dict=body.state,
            target_version=body.target_version,
            dry_run=body.dry_run,
        )

        return StateMigrateResponse(
            status="migrated" if result.success else "failed",
            success=result.success,
            from_version=result.from_version,
            to_version=result.to_version,
            changes_made=result.changes_made,
            warnings=result.warnings,
            state_after=result.state_after,
        )

    except Exception as exc:
        from app.logger import get_logger

        logger = get_logger("workflow_api")
        logger.error(
            "state_migration_failed",
            extra={"error": str(exc)[:500]},
        )
        raise
