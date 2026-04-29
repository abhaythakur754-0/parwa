"""
F-200: LangGraph Workflow Engine (Week 10 Day 12)

Orchestrates the AI response generation pipeline by building a
StateGraph with nodes for each pipeline step. Three variant tiers:

  - mini_parwa (L1):  3-step simplified pipeline
  - parwa      (L2):  6-step standard pipeline
  - high_parwa (L3):  9-step full pipeline

Each step is a node in the graph. The engine executes steps
sequentially, tracks per-step results, and handles timeouts.

Checkpointing:
  The workflow uses ``langgraph.checkpoint.memory.MemorySaver`` by
  default for in-process checkpoint persistence.  For production
  deployments, swap to one of:

    - ``langgraph-checkpoint-postgres``  (PostgreSQL-backed)
    - ``langgraph-checkpoint-redis``      (Redis-backed)

  Thread IDs are derived from ``conversation_id`` or ``ticket_id``
  so that each conversation gets its own checkpoint history.

Quality Gate Self-Correction Loop:
  After the ``quality_gate`` step, a conditional edge checks whether
  the confidence score meets the configured threshold.  If it falls
  below the threshold the graph routes back to ``generate`` for a
  retry (up to a configurable max-retry cap).  Otherwise execution
  continues to ``format``.

BC-001: All public methods take company_id as the first parameter.
BC-008: Every public method is wrapped in try/except; never crashes.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("langgraph_workflow")

# Production checkpointing backends (uncomment and configure as needed):
#   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
#   from langgraph.checkpoint.redis.aio import AsyncRedisSaver
# For development / single-process the in-memory checkpointer is sufficient.
_CHECKPOINT_BACKENDS_COMMENT = (
    "see langgraph-checkpoint-postgres / langgraph-checkpoint-redis"
)


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

_WORKFLOW_TIMEOUT_SECONDS: float = 30.0
_DEFAULT_MAX_TOKENS: int = 1500

# Maximum number of quality-gate retries before falling through to format.
# Prevents infinite self-correction loops.
_QUALITY_GATE_MAX_RETRIES: int = 3

# Default confidence threshold for the quality-gate conditional edge.
# If the quality_gate output score is below this value the graph routes
# back to ``generate`` for a retry.
_QUALITY_GATE_CONFIDENCE_THRESHOLD: float = 0.7

WORKFLOW_STEP_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "classify": {
        "step_id": "classify",
        "step_name": "Intent Classification",
        "step_type": "preprocessing",
        "estimated_tokens": 50,
        "timeout_seconds": 3.0,
    },
    "extract_signals": {
        "step_id": "extract_signals",
        "step_name": "Signal Extraction",
        "step_type": "preprocessing",
        "estimated_tokens": 100,
        "timeout_seconds": 4.0,
    },
    "technique_select": {
        "step_id": "technique_select",
        "step_name": "Technique Selection",
        "step_type": "preprocessing",
        "estimated_tokens": 50,
        "timeout_seconds": 3.0,
    },
    "context_compress": {
        "step_id": "context_compress",
        "step_name": "Context Compression",
        "step_type": "preprocessing",
        "estimated_tokens": 0,
        "timeout_seconds": 5.0,
    },
    "generate": {
        "step_id": "generate",
        "step_name": "Response Generation",
        "step_type": "core",
        "estimated_tokens": 800,
        "timeout_seconds": 15.0,
    },
    "quality_gate": {
        "step_id": "quality_gate",
        "step_name": "Quality Gate",
        "step_type": "postprocessing",
        "estimated_tokens": 200,
        "timeout_seconds": 5.0,
    },
    "context_health": {
        "step_id": "context_health",
        "step_name": "Context Health Check",
        "step_type": "postprocessing",
        "estimated_tokens": 50,
        "timeout_seconds": 3.0,
    },
    "dedup": {
        "step_id": "dedup",
        "step_name": "Deduplication",
        "step_type": "postprocessing",
        "estimated_tokens": 50,
        "timeout_seconds": 3.0,
    },
    "format": {
        "step_id": "format",
        "step_name": "Response Formatting",
        "step_type": "postprocessing",
        "estimated_tokens": 100,
        "timeout_seconds": 3.0,
    },
}

VARIANT_PIPELINE_CONFIG: Dict[str, Dict[str, Any]] = {
    "mini_parwa": {
        "steps": ["classify", "generate", "format"],
        "max_tokens": 1000,
        "timeout_seconds": 20.0,
        "description": "Simplified 3-step pipeline for L1 tier",
    },
    "parwa": {
        "steps": [
            "classify",
            "extract_signals",
            "technique_select",
            "generate",
            "quality_gate",
            "format",
        ],
        "max_tokens": 1500,
        "timeout_seconds": 30.0,
        "description": "Standard 6-step pipeline for L2 tier",
    },
    "high_parwa": {
        "steps": [
            "classify",
            "extract_signals",
            "technique_select",
            "context_compress",
            "generate",
            "quality_gate",
            "context_health",
            "dedup",
            "format",
        ],
        "max_tokens": 2000,
        "timeout_seconds": 30.0,
        "description": "Full 9-step pipeline for L3 tier",
    },
}


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class WorkflowConfig:
    """Configuration for a single workflow execution."""

    company_id: str = ""
    variant_type: str = "parwa"
    enable_context_compression: bool = False
    enable_context_health_check: bool = False
    max_pipeline_time_seconds: float = 30.0
    max_tokens: int = 1500
    # Checkpointer backend: "memory" (default), "postgres", or "redis".
    checkpointer_backend: str = "memory"
    # Confidence threshold for quality-gate self-correction loop.
    quality_gate_confidence_threshold: float = _QUALITY_GATE_CONFIDENCE_THRESHOLD
    # Maximum retries when quality gate fails.
    quality_gate_max_retries: int = _QUALITY_GATE_MAX_RETRIES


@dataclass
class WorkflowStep:
    """A single step within the pipeline graph."""

    step_id: str
    step_name: str
    step_type: str  # "preprocessing", "core", "postprocessing"
    estimated_tokens: int = 0
    timeout_seconds: float = 5.0
    enabled: bool = True


@dataclass
class WorkflowStepResult:
    """Outcome of executing a single pipeline step."""

    step_id: str
    status: str  # "success", "skipped", "error", "timeout"
    tokens_used: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    output: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Complete result of an entire workflow execution."""

    workflow_id: str
    variant_type: str
    status: str  # "success", "partial", "failed", "timeout"
    steps_completed: List[str] = field(default_factory=list)
    step_results: Dict[str, WorkflowStepResult] = field(
        default_factory=dict,
    )
    final_response: str = ""
    total_tokens_used: int = 0
    total_duration_ms: float = 0.0
    context_compression_applied: bool = False
    context_health_score: float = 1.0


# ══════════════════════════════════════════════════════════════════
# EXCEPTION
# ══════════════════════════════════════════════════════════════════


class WorkflowError(Exception):
    """Raised when a workflow encounters a critical failure.

    Inherits from Exception (not ParwaBaseError) because this is
    an internal engine error that should be caught by BC-008
    graceful degradation, not propagated to the API layer.
    """

    def __init__(
        self,
        message: str = "Workflow execution failed",
        workflow_id: str = "",
        step_id: str = "",
    ) -> None:
        self.message = message
        self.workflow_id = workflow_id
        self.step_id = step_id
        super().__init__(self.message)


# ══════════════════════════════════════════════════════════════════
# LANGGRAPH WORKFLOW ENGINE
# ══════════════════════════════════════════════════════════════════


class LangGraphWorkflow:
    """F-200: LangGraph Workflow Engine.

    Builds and executes a StateGraph-based pipeline for AI response
    generation. Supports three variant tiers with different pipeline
    topologies.

    The graph is lazily built on first execute() or when build_graph()
    is called explicitly. When the ``langgraph`` package is not
    installed the engine falls back to a simulation mode that still
    produces valid WorkflowResult objects (BC-008).

    BC-001: company_id first parameter on public methods.
    BC-008: Never crash — graceful degradation.
    """

    def __init__(
        self,
        config: Optional[WorkflowConfig] = None,
    ) -> None:
        self._config = config or WorkflowConfig()
        self._graph: Any = None  # lazy-built StateGraph
        self._steps: List[WorkflowStep] = []
        self._langgraph_available: Optional[bool] = None
        self._checkpointer: Any = None

        # Initialise the checkpointer based on config.
        self._init_checkpointer()

        logger.info(
            "workflow_engine_initialized",
            variant_type=self._config.variant_type,
            company_id=self._config.company_id,
            checkpointer_backend=self._config.checkpointer_backend,
            has_checkpointer=self._checkpointer is not None,
        )

    # ── Checkpointer Initialisation ─────────────────────────────

    def _init_checkpointer(self) -> None:
        """Initialise the LangGraph checkpointer.

        Uses ``MemorySaver`` (in-process, no external deps) by default.
        If the ``langgraph`` package is not installed the checkpointer
        stays ``None`` and execution degrades to the simulation path
        (BC-008).

        Production alternatives (set ``checkpointer_backend`` in config):
          - ``"postgres"`` → ``AsyncPostgresSaver`` from ``langgraph-checkpoint-postgres``
          - ``"redis"``   → ``AsyncRedisSaver``   from ``langgraph-checkpoint-redis``
        """
        backend = self._config.checkpointer_backend.lower()

        if backend == "memory":
            try:
                from langgraph.checkpoint.memory import MemorySaver

                self._checkpointer = MemorySaver()
                logger.info("checkpoint_memory_saver_initialized")
            except ImportError:
                logger.info(
                    "checkpoint_memory_saver_unavailable",
                    detail="langgraph not installed; checkpointing disabled",
                )
                self._checkpointer = None
        elif backend == "postgres":
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

                self._checkpointer = AsyncPostgresSaver.from_conn_string(
                    "",  # Caller must call setup() with the real DSN
                )
                logger.info("checkpoint_postgres_saver_initialized")
            except ImportError:
                logger.warning(
                    "checkpoint_postgres_saver_unavailable",
                    detail="langgraph-checkpoint-postgres not installed; falling back to memory",
                )
                self._init_checkpointer()  # recurse into "memory"
        elif backend == "redis":
            try:
                from langgraph.checkpoint.redis.aio import AsyncRedisSaver

                self._checkpointer = AsyncRedisSaver.from_url(
                    "",  # Caller must call setup() with the real URL
                )
                logger.info("checkpoint_redis_saver_initialized")
            except ImportError:
                logger.warning(
                    "checkpoint_redis_saver_unavailable",
                    detail="langgraph-checkpoint-redis not installed; falling back to memory",
                )
                self._init_checkpointer()  # recurse into "memory"
        else:
            logger.warning(
                "checkpoint_unknown_backend",
                backend=backend,
                detail="No checkpointer initialised",
            )

    # ── Graph Construction ─────────────────────────────────────

    def build_graph(self) -> None:
        """Build the pipeline graph based on variant_type.

        Determines which steps to include and in what order.
        If langgraph is available, creates a StateGraph; otherwise
        stores the step list for simulated execution.
        """
        variant = self._config.variant_type
        self._steps = self._build_steps_for_variant(variant)

        logger.info(
            "workflow_graph_built",
            variant_type=variant,
            step_count=len(self._steps),
            company_id=self._config.company_id,
        )

        # Try to build actual LangGraph StateGraph
        try:
            self._build_langgraph_stategraph()
        except Exception as exc:
            logger.warning(
                "langgraph_build_fallback",
                error=str(exc),
                company_id=self._config.company_id,
            )
            self._langgraph_available = False

    def _build_langgraph_stategraph(self) -> None:
        """Attempt to build a real LangGraph StateGraph.

        Creates nodes for each pipeline step and wires them with
        sequential edges.  When a ``quality_gate`` step is present
        a conditional edge is added that routes back to ``generate``
        if the confidence score is below the configured threshold,
        creating a self-correction loop (capped at
        ``quality_gate_max_retries``).

        Compiles with the configured checkpointer (MemorySaver by
        default) so that every node execution is persisted as a
        checkpoint keyed by ``thread_id``.  Falls back gracefully
        when langgraph is not installed (BC-008).
        """
        try:
            import operator
            from typing import Annotated, TypedDict

            from langgraph.graph import END, StateGraph

            # Define the graph state schema
            class WorkflowState(TypedDict):
                query: str
                company_id: str
                variant_type: str
                context: dict
                step_outputs: Annotated[dict, operator.or_]
                final_response: str
                total_tokens: int
                errors: list
                quality_retries: int  # counter for self-correction loop

            builder = StateGraph(WorkflowState)

            # Register a node for each step in the pipeline
            step_ids = [s.step_id for s in self._steps]
            for step_id in step_ids:

                async def _node_fn(state: dict, _sid=step_id) -> dict:
                    """Delegate to the real step executor."""
                    try:
                        # Find the WorkflowStep definition for this step_id
                        wf_step = next(
                            (s for s in self._steps if s.step_id == _sid),
                            None,
                        )
                        if wf_step is None:
                            return {
                                "step_outputs": {
                                    _sid: {"status": "error", "error": "Unknown step"},
                                },
                                "errors": state.get("errors", [])
                                + [f"Unknown step: {_sid}"],
                            }

                        # Reconstruct step_results from accumulated state so
                        # downstream steps (e.g. generate) can read upstream outputs
                        # (e.g. classify intent, technique_select technique).
                        prev_outputs = state.get("step_outputs", {})
                        reconstructed: Dict[str, WorkflowStepResult] = {}
                        for prev_sid, prev_out in prev_outputs.items():
                            if isinstance(prev_out, dict):
                                reconstructed[prev_sid] = WorkflowStepResult(
                                    step_id=prev_sid,
                                    status=prev_out.get("status", "unknown"),
                                    tokens_used=prev_out.get("tokens_used", 0),
                                    output=prev_out.get("output", {}),
                                )

                        step_result = await self._execute_step(
                            company_id=state.get("company_id", self._config.company_id),
                            wf_step=wf_step,
                            query=state.get("query", ""),
                            context=state.get("context", {}),
                            step_results=reconstructed,
                        )

                        node_return: Dict[str, Any] = {
                            "step_outputs": {
                                _sid: {
                                    "status": step_result.status,
                                    "tokens_used": step_result.tokens_used,
                                    "duration_ms": step_result.duration_ms,
                                    "output": step_result.output,
                                    "error": step_result.error,
                                },
                            },
                            "final_response": (
                                step_result.output.get("response", "")
                                if _sid == "generate"
                                and step_result.status == "success"
                                else state.get("final_response", "")
                            ),
                            "total_tokens": (
                                state.get("total_tokens", 0) + step_result.tokens_used
                            ),
                            "errors": (
                                state.get("errors", []) + [step_result.error]
                                if step_result.error
                                else state.get("errors", [])
                            ),
                        }

                        # Increment quality_retries when re-entering generate
                        if _sid == "generate":
                            node_return["quality_retries"] = (
                                state.get("quality_retries", 0) + 1
                            )

                        return node_return
                    except Exception as exc:
                        logger.warning(
                            "langgraph_node_error",
                            step_id=_sid,
                            error=str(exc),
                        )
                        return {
                            "step_outputs": {
                                _sid: {"status": "error", "error": str(exc)},
                            },
                            "errors": state.get("errors", []) + [str(exc)],
                        }

                builder.add_node(step_id, _node_fn)

            # Wire edges sequentially, with conditional edge after quality_gate
            has_quality_gate = "quality_gate" in step_ids
            generate_idx = step_ids.index("generate") if "generate" in step_ids else -1

            for i in range(len(step_ids) - 1):
                src = step_ids[i]
                dst = step_ids[i + 1]

                # If this is the quality_gate step, use a conditional edge
                # instead of a direct edge to the next step.
                if src == "quality_gate" and has_quality_gate:
                    # Find the node that follows quality_gate (usually
                    # "format")
                    next_after_qg = step_ids[i + 1]

                    def _quality_gate_router(state: dict) -> str:
                        """Route based on quality gate confidence score.

                        If the score is below the threshold AND we have not
                        exceeded max retries, route back to ``generate``.
                        Otherwise continue to the next step (e.g. ``format``).
                        """
                        qg_output = state.get("step_outputs", {}).get(
                            "quality_gate", {}
                        )
                        score = (
                            qg_output.get("output", {}).get("score", 1.0)
                            if isinstance(qg_output, dict)
                            else 1.0
                        )
                        retries = state.get("quality_retries", 0)
                        threshold = self._config.quality_gate_confidence_threshold
                        max_retries = self._config.quality_gate_max_retries

                        if score < threshold and retries < max_retries:
                            logger.info(
                                "quality_gate_retry",
                                score=round(score, 3),
                                threshold=threshold,
                                retries=retries,
                                max_retries=max_retries,
                            )
                            return "generate"
                        return next_after_qg

                    builder.add_conditional_edges(
                        "quality_gate",
                        _quality_gate_router,
                        {"generate": "generate", next_after_qg: next_after_qg},
                    )
                    # Skip the normal sequential edge for quality_gate
                    # (the conditional edge handles routing).
                    continue

                builder.add_edge(src, dst)

            # Last step → END  (only if it wasn't already handled above)
            if step_ids and step_ids[-1] != "quality_gate":
                builder.add_edge(step_ids[-1], END)
            elif has_quality_gate:
                # quality_gate is the last step — its conditional edge
                # already routes to the next node or generate; the
                # last non-conditional step needs an END edge.
                # Find the step after quality_gate in the original list.
                qg_idx = step_ids.index("quality_gate")
                if qg_idx + 1 < len(step_ids):
                    # The next step (e.g. format) should connect to END
                    builder.add_edge(step_ids[qg_idx + 1], END)

            # ── Compile with checkpointer ────────────────────────
            compile_kwargs: Dict[str, Any] = {}
            if self._checkpointer is not None:
                compile_kwargs["checkpointer"] = self._checkpointer
                logger.info(
                    "checkpoint_compile_with_checkpointer",
                    checkpointer_type=type(self._checkpointer).__name__,
                )
            else:
                logger.info("checkpoint_compile_without_checkpointer")

            self._graph = builder.compile(**compile_kwargs)
            self._langgraph_available = True
            logger.info(
                "langgraph_stategraph_built",
                company_id=self._config.company_id,
                variant_type=self._config.variant_type,
                node_count=len(step_ids),
                has_checkpointer=self._checkpointer is not None,
                has_quality_gate_loop=has_quality_gate,
            )
        except ImportError:
            self._langgraph_available = False
            logger.info(
                "langgraph_not_available_using_simulation",
                company_id=self._config.company_id,
            )
        except Exception as exc:
            self._langgraph_available = False
            logger.warning(
                "langgraph_stategraph_build_error",
                error=str(exc),
                company_id=self._config.company_id,
            )

    def _build_steps_for_variant(
        self,
        variant_type: str,
    ) -> List[WorkflowStep]:
        """Build the step list for a given variant."""
        builders = {
            "mini_parwa": self._build_mini_parwa_pipeline,
            "parwa": self._build_parwa_pipeline,
            "high_parwa": self._build_high_parwa_pipeline,
        }
        builder = builders.get(variant_type, self._build_parwa_pipeline)
        return builder()

    def _make_step(self, step_id: str) -> WorkflowStep:
        """Create a WorkflowStep from the step definition registry."""
        definition = WORKFLOW_STEP_DEFINITIONS.get(step_id, {})
        return WorkflowStep(
            step_id=step_id,
            step_name=definition.get("step_name", step_id),
            step_type=definition.get("step_type", "core"),
            estimated_tokens=definition.get(
                "estimated_tokens",
                0,
            ),
            timeout_seconds=definition.get(
                "timeout_seconds",
                5.0,
            ),
            enabled=True,
        )

    # ── Variant Pipelines ──────────────────────────────────────

    def _build_mini_parwa_pipeline(self) -> List[WorkflowStep]:
        """3-step simplified pipeline: classify -> generate -> format."""
        return [
            self._make_step("classify"),
            self._make_step("generate"),
            self._make_step("format"),
        ]

    def _build_parwa_pipeline(self) -> List[WorkflowStep]:
        """6-step standard pipeline.

        classify -> extract_signals -> technique_select ->
        generate -> quality_gate -> format
        """
        step_ids = [
            "classify",
            "extract_signals",
            "technique_select",
            "generate",
            "quality_gate",
            "format",
        ]
        return [self._make_step(sid) for sid in step_ids]

    def _build_high_parwa_pipeline(self) -> List[WorkflowStep]:
        """9-step full pipeline.

        classify -> extract_signals -> technique_select ->
        context_compress -> generate -> quality_gate ->
        context_health -> dedup -> format
        """
        step_ids = [
            "classify",
            "extract_signals",
            "technique_select",
            "context_compress",
            "generate",
            "quality_gate",
            "context_health",
            "dedup",
            "format",
        ]
        return [self._make_step(sid) for sid in step_ids]

    # ── Execution ──────────────────────────────────────────────

    async def execute(
        self,
        company_id: str,
        query: str,
        **kwargs: Any,
    ) -> WorkflowResult:
        """Execute the full workflow end-to-end.

        Runs each step sequentially, collects results, and returns
        a WorkflowResult. Falls back to simulation if langgraph is
        not available (BC-008).

        Args:
            company_id: Tenant company ID (BC-001).
            query: The user's input query.
            **kwargs: Optional context such as conversation_history,
                knowledge_context, customer_sentiment, etc.

        Returns:
            WorkflowResult with per-step details and final response.
        """
        workflow_id = str(uuid.uuid4())[:8]
        variant = self._config.variant_type
        pipeline_start = time.monotonic()

        # Derive thread_id from conversation_id or ticket_id for checkpointing.
        # Falls back to a new UUID if neither is provided (one-shot execution).
        thread_id = (
            kwargs.get("conversation_id")
            or kwargs.get("ticket_id")
            or f"wf-{workflow_id}"
        )

        try:
            # Lazy-build graph if not yet built
            if not self._steps:
                self.build_graph()

            logger.info(
                "workflow_execution_started",
                workflow_id=workflow_id,
                company_id=company_id,
                variant_type=variant,
                step_count=len(self._steps),
                query_length=len(query),
            )

            step_results: Dict[str, WorkflowStepResult] = {}
            steps_completed: List[str] = []
            total_tokens = 0
            final_response = ""
            compression_applied = False
            health_score = 1.0
            pipeline_timed_out = False
            overall_status = "success"

            config = VARIANT_PIPELINE_CONFIG.get(
                variant,
                VARIANT_PIPELINE_CONFIG["parwa"],
            )
            max_time = config.get(
                "timeout_seconds",
                _WORKFLOW_TIMEOUT_SECONDS,
            )

            # Try LangGraph execution first (preferred path)
            if self._langgraph_available and self._graph is not None:
                graph_result = await self._execute_via_langgraph(
                    company_id=company_id,
                    query=query,
                    variant=variant,
                    max_time=max_time,
                    pipeline_start=pipeline_start,
                    workflow_id=workflow_id,
                    thread_id=thread_id,
                    **kwargs,
                )
                if graph_result is not None:
                    return graph_result
                # Fall through to sequential execution if graph failed
                logger.warning(
                    "langgraph_fallback_to_sequential",
                    workflow_id=workflow_id,
                    company_id=company_id,
                )

            for wf_step in self._steps:
                if not wf_step.enabled:
                    step_results[wf_step.step_id] = WorkflowStepResult(
                        step_id=wf_step.step_id,
                        status="skipped",
                    )
                    continue

                # Check pipeline timeout
                elapsed = time.monotonic() - pipeline_start
                if elapsed >= max_time:
                    pipeline_timed_out = True
                    step_results[wf_step.step_id] = WorkflowStepResult(
                        step_id=wf_step.step_id,
                        status="timeout",
                        duration_ms=0.0,
                        error="Pipeline timeout exceeded",
                    )
                    overall_status = "timeout"
                    logger.warning(
                        "workflow_pipeline_timeout",
                        workflow_id=workflow_id,
                        company_id=company_id,
                        elapsed_ms=round(elapsed * 1000, 2),
                        max_ms=round(max_time * 1000, 2),
                    )
                    break

                # Execute single step
                step_start = time.monotonic()
                step_result = await self._execute_step(
                    company_id=company_id,
                    wf_step=wf_step,
                    query=query,
                    context=kwargs,
                    step_results=step_results,
                )
                step_elapsed_ms = (time.monotonic() - step_start) * 1000
                step_result.duration_ms = round(step_elapsed_ms, 2)

                step_results[wf_step.step_id] = step_result
                total_tokens += step_result.tokens_used

                if step_result.status == "success":
                    steps_completed.append(wf_step.step_id)
                    # Capture special outputs
                    if wf_step.step_id == "context_compress":
                        compression_applied = step_result.output.get(
                            "compressed",
                            False,
                        )
                    if wf_step.step_id == "context_health":
                        health_score = step_result.output.get(
                            "health_score",
                            1.0,
                        )
                    if wf_step.step_id == "generate":
                        final_response = step_result.output.get(
                            "response",
                            "",
                        )
                elif step_result.status == "timeout":
                    overall_status = "partial"
                elif step_result.status == "error":
                    # BC-008: Continue pipeline on step error
                    overall_status = "partial"
                    logger.warning(
                        "workflow_step_error_continuing",
                        workflow_id=workflow_id,
                        step_id=wf_step.step_id,
                        error=step_result.error,
                        company_id=company_id,
                    )

            total_duration_ms = (time.monotonic() - pipeline_start) * 1000

            result = WorkflowResult(
                workflow_id=workflow_id,
                variant_type=variant,
                status=overall_status,
                steps_completed=steps_completed,
                step_results=step_results,
                final_response=final_response,
                total_tokens_used=total_tokens,
                total_duration_ms=round(total_duration_ms, 2),
                context_compression_applied=compression_applied,
                context_health_score=health_score,
            )

            logger.info(
                "workflow_execution_completed",
                workflow_id=workflow_id,
                company_id=company_id,
                status=overall_status,
                steps_completed=len(steps_completed),
                total_tokens=total_tokens,
                duration_ms=round(total_duration_ms, 2),
            )

            return result

        except Exception as exc:
            # BC-008: Graceful degradation — never crash
            logger.warning(
                "workflow_execution_failed",
                error=str(exc),
                workflow_id=workflow_id,
                company_id=company_id,
            )
            total_duration_ms = (time.monotonic() - pipeline_start) * 1000
            return WorkflowResult(
                workflow_id=workflow_id,
                variant_type=self._config.variant_type,
                status="failed",
                total_duration_ms=round(total_duration_ms, 2),
                final_response="",
            )

    async def _execute_step(
        self,
        company_id: str,
        wf_step: WorkflowStep,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> WorkflowStepResult:
        """Execute a single workflow step.

        Dispatches to real AI-backed handlers when langgraph and
        the component modules are available, otherwise falls back
        to simulation (BC-008).
        """
        step_id = wf_step.step_id

        try:
            # ── Real AI path ──────────────────────────────────
            if self._langgraph_available:
                try:
                    output, tokens = await self._execute_real_step(
                        company_id=company_id,
                        step_id=step_id,
                        step_type=wf_step.step_type,
                        query=query,
                        context=context,
                        step_results=step_results,
                    )
                    return WorkflowStepResult(
                        step_id=step_id,
                        status="success",
                        tokens_used=tokens,
                        output=output,
                    )
                except Exception as real_exc:
                    # BC-008: Fall back to simulation on real-step failure
                    logger.warning(
                        "real_step_failed_falling_back_to_simulation",
                        step_id=step_id,
                        error=str(real_exc),
                        company_id=company_id,
                    )

            # ── Simulation fallback path ─────────────────────
            if wf_step.step_type == "preprocessing":
                output, tokens = self._simulate_preprocessing(
                    step_id,
                    query,
                    context,
                    step_results,
                )
            elif wf_step.step_type == "core":
                output, tokens = self._simulate_core_step(
                    step_id,
                    query,
                    context,
                    step_results,
                )
            else:
                output, tokens = self._simulate_postprocessing(
                    step_id,
                    query,
                    context,
                    step_results,
                )

            return WorkflowStepResult(
                step_id=step_id,
                status="success",
                tokens_used=tokens,
                output=output,
            )
        except Exception as exc:
            logger.warning(
                "workflow_step_execution_error",
                step_id=step_id,
                error=str(exc),
                company_id=company_id,
            )
            return WorkflowStepResult(
                step_id=step_id,
                status="error",
                error=str(exc),
            )

    async def _execute_via_langgraph(
        self,
        company_id: str,
        query: str,
        variant: str,
        max_time: float,
        pipeline_start: float,
        workflow_id: str,
        thread_id: str = "",
        **kwargs: Any,
    ) -> Optional[WorkflowResult]:
        """Execute the pipeline using the compiled LangGraph StateGraph.

        This is the preferred execution path when langgraph is available,
        as it leverages the graph's built-in state management and error
        handling. Falls back to sequential execution if graph invocation
        fails (BC-008).

        The ``thread_id`` is used as the checkpoint key so that the
        workflow can be resumed later for the same conversation.
        """
        try:
            initial_state = {
                "query": query,
                "company_id": company_id,
                "variant_type": variant,
                "context": kwargs,
                "step_outputs": {},
                "final_response": "",
                "total_tokens": 0,
                "errors": [],
                "quality_retries": 0,
            }

            # Build checkpoint config with thread_id for persistence
            config: Dict[str, Any] = {
                "configurable": {
                    "workflow_id": workflow_id,
                    "thread_id": thread_id,
                },
            }

            logger.info(
                "checkpoint_invoking_graph",
                workflow_id=workflow_id,
                thread_id=thread_id,
                has_checkpointer=self._checkpointer is not None,
            )

            final_state = await self._graph.ainvoke(initial_state, config)

            logger.info(
                "checkpoint_graph_invocation_complete",
                workflow_id=workflow_id,
                thread_id=thread_id,
            )

            # Parse results from graph state
            step_outputs = final_state.get("step_outputs", {})
            step_results: Dict[str, WorkflowStepResult] = {}
            steps_completed: List[str] = []
            total_tokens = final_state.get("total_tokens", 0)
            final_response = final_state.get("final_response", "")
            errors = final_state.get("errors", [])
            overall_status = "success"

            for step_id, output in step_outputs.items():
                step_results[step_id] = WorkflowStepResult(
                    step_id=step_id,
                    status=output.get("status", "unknown"),
                    tokens_used=output.get("tokens_used", 0),
                    duration_ms=output.get("duration_ms", 0.0),
                    error=output.get("error"),
                    output=output.get("output", {}),
                )
                if output.get("status") == "success":
                    steps_completed.append(step_id)
                elif output.get("status") in ("error", "timeout"):
                    overall_status = "partial"

            if errors:
                overall_status = "partial"

            total_duration_ms = round((time.monotonic() - pipeline_start) * 1000, 2)

            logger.info(
                "langgraph_execution_completed",
                workflow_id=workflow_id,
                company_id=company_id,
                thread_id=thread_id,
                status=overall_status,
                steps_completed=len(steps_completed),
                total_tokens=total_tokens,
                duration_ms=total_duration_ms,
            )

            return WorkflowResult(
                workflow_id=workflow_id,
                variant_type=variant,
                status=overall_status,
                steps_completed=steps_completed,
                step_results=step_results,
                final_response=final_response,
                total_tokens_used=total_tokens,
                total_duration_ms=total_duration_ms,
            )

        except Exception as exc:
            logger.warning(
                "langgraph_execution_failed_falling_back_to_sequential",
                error=str(exc),
                workflow_id=workflow_id,
                company_id=company_id,
                thread_id=thread_id,
            )
            return None  # Signals caller to fall back to sequential execution

    # ── Real AI Step Execution ──────────────────────────────

    async def _execute_real_step(
        self,
        company_id: str,
        step_id: str,
        step_type: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Execute a step using real AI-backed components.

        Each sub-call is wrapped in try/except so that a single
        component failure degrades gracefully to simulation (BC-008).
        Lazy imports keep optional dependencies from breaking startup.
        """
        if step_id == "classify":
            return await self._real_classify(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "extract_signals":
            return await self._real_extract_signals(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "technique_select":
            return await self._real_technique_select(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "context_compress":
            return await self._real_context_compress(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "generate":
            return await self._real_generate(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "quality_gate":
            return await self._real_quality_gate(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "context_health":
            return await self._real_context_health(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "dedup":
            return self._real_dedup(
                company_id,
                query,
                context,
                step_results,
            )
        if step_id == "format":
            return self._real_format(
                company_id,
                query,
                context,
                step_results,
            )

        # Unknown step — let the caller fall back to simulation
        raise NotImplementedError(f"No real handler for step '{step_id}'")

    # ── Individual real step handlers ────────────────────────

    async def _real_classify(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use ClassificationEngine for real intent classification.

        B6 FIX: Read primary_confidence (not confidence). IntentResult has
        no tokens_used field — estimate from processing_time_ms.
        """
        from app.core.classification_engine import ClassificationEngine

        engine = ClassificationEngine()
        intent_result = await engine.classify(
            text=query,
            company_id=company_id,
            variant_type=self._config.variant_type,
            use_ai=True,
        )
        # Estimate tokens: ~4 tokens per ms of processing time, min 50
        estimated_tokens = max(50, int(intent_result.processing_time_ms * 4))
        return {
            "intent": intent_result.primary_intent,
            "confidence": intent_result.primary_confidence,
            "secondary_intents": intent_result.secondary_intents,
            "method": intent_result.classification_method,
        }, estimated_tokens

    async def _real_extract_signals(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use SignalExtractor for real signal extraction."""
        from app.core.signal_extraction import (
            SignalExtractionRequest,
            SignalExtractor,
        )

        extractor = SignalExtractor()
        request = SignalExtractionRequest(
            query=query,
            company_id=company_id,
            variant_type=self._config.variant_type,
            customer_tier=context.get("customer_tier", "free"),
            turn_count=context.get("turn_count", 0),
            conversation_history=context.get("conversation_history"),
        )
        signals = await extractor.extract(request)
        return signals.to_dict(), 100

    async def _real_technique_select(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use TechniqueRouter for real technique selection.

        B8 FIX: Include frustration_score derived from sentiment score
        in extract_signals output. Convert 0.0-1.0 sentiment → 0-100
        frustration (inverted: low sentiment = high frustration).
        """
        from app.core.technique_router import (
            QuerySignals,
            TechniqueRouter,
        )

        # Build QuerySignals from classify & extract_signals results
        classify_out = {}
        classify_step = step_results.get("classify")
        if classify_step and classify_step.output:
            classify_out = classify_step.output

        extract_out = {}
        extract_step = step_results.get("extract_signals")
        if extract_step and extract_step.output:
            extract_out = extract_step.output

        # B8: Derive frustration from sentiment (inverse: sentiment 0.0 =
        # frustration 100)
        sentiment_val = extract_out.get("sentiment", 0.7)
        frustration_est = round(max(0.0, min(100.0, (1.0 - sentiment_val) * 100.0)), 1)

        signals = QuerySignals(
            query_complexity=extract_out.get("complexity", 0.5),
            confidence_score=classify_out.get("confidence", 0.8),
            sentiment_score=extract_out.get("sentiment", 0.7),
            frustration_score=frustration_est,
            intent_type=classify_out.get("intent", "general"),
            customer_tier=extract_out.get("customer_tier", "free"),
            monetary_value=extract_out.get("monetary_value", 0.0),
            turn_count=extract_out.get("turn_count", 0),
            previous_response_status=extract_out.get(
                "previous_response_status",
                "none",
            ),
            reasoning_loop_detected=extract_out.get(
                "reasoning_loop_detected",
                False,
            ),
            resolution_path_count=extract_out.get(
                "resolution_path_count",
                1,
            ),
        )

        router = TechniqueRouter()
        result = router.route(signals)

        activated = [ta.technique_id.value for ta in result.activated_techniques]
        return {
            "technique": activated[0] if activated else "standard_response",
            "activated_techniques": activated,
            "model_tier": result.model_tier,
            "trigger_rules_matched": result.trigger_rules_matched,
            "method": "ai",
        }, 50

    async def _real_context_compress(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use ContextCompressor for real context compression."""
        from app.core.context_compression import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        # Gather context content to compress
        raw_context = (
            context.get("knowledge_context")
            or context.get("conversation_history")
            or []
        )
        if isinstance(raw_context, str):
            content_chunks = [raw_context]
        elif isinstance(raw_context, list):
            content_chunks = [
                chunk if isinstance(chunk, str) else str(chunk) for chunk in raw_context
            ]
        else:
            content_chunks = [str(raw_context)]

        input_data = CompressionInput(
            content=content_chunks,
            token_counts=[len(c.split()) for c in content_chunks],
            priorities=[1.0] * len(content_chunks),
            metadata={"query": query},
        )

        output = await compressor.compress(company_id, input_data)
        return {
            "compressed": output.chunks_removed > 0,
            "original_tokens": output.original_token_count,
            "compressed_tokens": output.compressed_token_count,
            "compression_ratio": output.compression_ratio,
            "strategy_used": output.strategy_used,
            "method": "ai",
        }, max(output.original_token_count - output.compressed_token_count, 0)

    async def _real_generate(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use SmartRouter for real LLM response generation."""
        from app.core.smart_router import (
            AtomicStepType,
            SmartRouter,
        )

        router = SmartRouter()

        # Build query signals for routing
        query_signals: Dict[str, Any] = {}
        classify_step = step_results.get("classify")
        if classify_step and classify_step.output:
            query_signals["intent"] = classify_step.output.get("intent")
            query_signals["confidence"] = classify_step.output.get("confidence")

        # Route to the best model for draft generation
        routing_decision = router.route(
            company_id=company_id,
            variant_type=self._config.variant_type,
            atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
            query_signals=query_signals,
        )

        # Build messages payload — inject full session context
        system_prompt = (
            context.get("system_prompt", "")
            or "You are a helpful customer support assistant."
        )
        knowledge_ctx = context.get("knowledge_context", "")
        if knowledge_ctx and isinstance(knowledge_ctx, (list, str)):
            if isinstance(knowledge_ctx, list):
                knowledge_ctx = "\n".join(str(k) for k in knowledge_ctx)
            system_prompt += f"\n\nRelevant context:\n{knowledge_ctx}"

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Inject conversation history so the AI has full session context
        conversation_history = context.get("conversation_history")
        if conversation_history and isinstance(conversation_history, list):
            for msg in conversation_history[-20:]:  # Last 20 turns
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    # Map internal "jarvis" role to standard "assistant" role
                    # (AI APIs only accept system/user/assistant)
                    role = msg["role"]
                    if role == "jarvis":
                        role = "assistant"
                    messages.append(
                        {
                            "role": role,
                            "content": msg["content"],
                        }
                    )

        # Append current query
        messages.append({"role": "user", "content": query})

        # Execute the LLM call (async)
        llm_result = await router.async_execute_llm_call(
            company_id=company_id,
            routing_decision=routing_decision,
            messages=messages,
            temperature=0.7,
            max_tokens=self._config.max_tokens,
        )

        response_text = llm_result.get("content", "")
        # Use real token count from LiteLLM response if available
        tokens_used = llm_result.get("tokens_used", len(response_text.split()) * 4)

        return {
            "response": response_text,
            "model": routing_decision.model_config.model_id,
            "provider": routing_decision.provider.value,
            "tier": routing_decision.tier.value,
            "finish_reason": llm_result.get("finish_reason", "stop"),
            "method": "ai",
        }, tokens_used

    async def _real_quality_gate(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use CLARAQualityGate for real quality evaluation."""
        from app.core.clara_quality_gate import CLARAQualityGate

        # Get the generated response from the generate step
        gen_step = step_results.get("generate")
        response = ""
        if gen_step and gen_step.output:
            response = gen_step.output.get("response", "")

        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response=response,
            query=query,
            company_id=company_id,
            customer_sentiment=context.get("customer_sentiment", 0.7),
            context=context,
        )

        return {
            "passed": result.passed,
            "score": result.overall_score,
            "issues": [
                {"stage": s.stage.value, "status": s.result.value}
                for s in result.stages
                if s.result.value != "pass"
            ],
            "stage_details": [
                {"stage": s.stage.value, "status": s.result.value, "score": s.score}
                for s in result.stages
            ],
            "method": "ai",
        }, 200

    async def _real_context_health(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use ContextHealthMeter for real context health check."""
        from app.core.context_health import (
            ContextHealthMeter,
            HealthMetrics,
        )

        meter = ContextHealthMeter()
        conversation_id = context.get("conversation_id", "default")
        turn_number = context.get("turn_count", 0)

        metrics = HealthMetrics(
            token_usage_ratio=context.get("token_usage_ratio", 0.5),
            compression_ratio=context.get("compression_ratio", 1.0),
            relevance_score=context.get("relevance_score", 0.9),
            freshness_score=context.get("freshness_score", 1.0),
            signal_preservation=context.get("signal_preservation", 1.0),
            context_coherence=context.get("context_coherence", 0.9),
        )

        report = await meter.check_health(
            company_id=company_id,
            conversation_id=str(conversation_id),
            metrics=metrics,
            turn_number=turn_number,
        )

        return {
            "health_score": report.overall_score,
            "status": report.status.value,
            "alerts": [
                {"type": a.alert_type.value, "message": a.message}
                for a in report.alerts
            ],
            "recommendations": report.recommendations,
            "method": "ai",
        }, 50

    def _real_dedup(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Check for duplicate content in the generated response."""
        gen_step = step_results.get("generate")
        response = ""
        if gen_step and gen_step.output:
            response = gen_step.output.get("response", "")

        # Simple sentence-level dedup check
        sentences = [s.strip() for s in response.split(".") if s.strip()]
        seen: Dict[str, int] = {}
        duplicates = 0
        for sentence in sentences:
            normalized = sentence.lower().strip()
            if normalized in seen:
                duplicates += 1
            else:
                seen[normalized] = 1

        dedup_applied = duplicates > 0
        if dedup_applied:
            # Keep first occurrence of each sentence
            unique_sentences = list(
                dict.fromkeys(s.strip() for s in response.split(".") if s.strip())
            )
            context["deduped_response"] = ". ".join(unique_sentences) + "."

        return {
            "dedup_applied": dedup_applied,
            "duplicates_found": duplicates,
            "total_sentences": len(sentences),
            "method": "rule",
        }, 50

    def _real_format(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Format the final response, applying dedup if available."""
        gen_step = step_results.get("generate")
        raw_response = ""
        if gen_step and gen_step.output:
            raw_response = gen_step.output.get("response", "")

        # Use deduped response if dedup ran
        formatted = context.pop("deduped_response", raw_response)

        # Basic formatting: trim whitespace, ensure single trailing newline
        formatted = formatted.strip()
        if not formatted.endswith(".") and len(formatted) > 10:
            formatted += "."

        return {
            "formatted_response": formatted,
            "format_type": "text",
            "method": "rule",
        }, 100

    # ── Simulation Methods (fallback) ─────────────────────────

    def _simulate_preprocessing(
        self,
        step_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Simulate a preprocessing step output."""
        tokens = WORKFLOW_STEP_DEFINITIONS.get(
            step_id,
            {},
        ).get("estimated_tokens", 50)

        if step_id == "classify":
            # Classify intent from query length and content
            intent = "general_inquiry"
            q_lower = query.lower()
            if any(w in q_lower for w in ["refund", "cancel", "return", "money"]):
                intent = "refund_request"
            elif any(w in q_lower for w in ["order", "ship", "track", "delivery"]):
                intent = "order_status"
            elif any(w in q_lower for w in ["error", "bug", "broken", "not work"]):
                intent = "technical_issue"
            return {
                "intent": intent,
                "confidence": 0.85,
            }, tokens

        if step_id == "extract_signals":
            signals = []
            q_lower = query.lower()
            if "urgent" in q_lower or "asap" in q_lower:
                signals.append("urgency_high")
            if "?" in query:
                signals.append("has_question")
            signals.append("query_length_" + str(len(query)))
            return {"signals": signals}, tokens

        if step_id == "technique_select":
            prev_classify = step_results.get("classify")
            intent = (
                prev_classify.output.get("intent", "general")
                if prev_classify
                else "general"
            )
            technique = "standard_response"
            if intent == "refund_request":
                technique = "refund_handling"
            elif intent == "technical_issue":
                technique = "troubleshooting"
            return {"technique": technique}, tokens

        if step_id == "context_compress":
            return {
                "compressed": True,
                "original_tokens": context.get(
                    "context_tokens",
                    500,
                ),
                "compressed_tokens": context.get(
                    "context_tokens",
                    500,
                )
                * 0.7,
            }, tokens

        return {"raw_output": True}, tokens

    def _simulate_core_step(
        self,
        step_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Simulate a core processing step output.

        Context-aware: incorporates system_prompt context, detected
        intent, technique, and conversation history so the simulated
        response is relevant rather than generic.
        """
        tokens = WORKFLOW_STEP_DEFINITIONS.get(
            step_id,
            {},
        ).get("estimated_tokens", 500)

        if step_id == "generate":
            technique = "standard_response"
            tech_step = step_results.get("technique_select")
            if tech_step and tech_step.output:
                technique = tech_step.output.get(
                    "technique",
                    technique,
                )

            # Extract context-aware details from the system prompt
            system_prompt = context.get("system_prompt", "")
            industry = ""
            pages = ""
            stage = ""
            if system_prompt:
                # Quick extraction of context hints from system prompt
                for line in system_prompt.split("\n"):
                    line_s = line.strip().lower()
                    if line_s.startswith("- industry:"):
                        industry = line.split(":", 1)[1].strip()
                    elif line_s.startswith("- pages visited:"):
                        pages = line.split(":", 1)[1].strip()
                    elif line_s.startswith("- conversation stage:"):
                        stage = line.split(":", 1)[1].strip()

            # Build a contextually relevant response
            context_hints = []
            if industry:
                context_hints.append(f"in the {industry} space")
            if pages:
                context_hints.append(f"based on your exploration of {pages}")
            if stage:
                context_hints.append(f"(stage: {stage})")

            hint_str = " ".join(context_hints)
            response = (
                "Thank you for your message. "
                f"Regarding your query about '{query[:50]}', "
                f"I'd be happy to help{(' ' + hint_str) if hint_str else ''}. "
                f"[Technique: {technique}]"
            )
            return {
                "response": response,
                "model": "simulation",
                "finish_reason": "stop",
            }, tokens

        return {"raw_output": True}, tokens

    def _simulate_postprocessing(
        self,
        step_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Simulate a postprocessing step output."""
        tokens = WORKFLOW_STEP_DEFINITIONS.get(
            step_id,
            {},
        ).get("estimated_tokens", 50)

        if step_id == "quality_gate":
            return {
                "passed": True,
                "score": 0.92,
                "issues": [],
            }, tokens

        if step_id == "context_health":
            return {
                "health_score": 0.95,
                "status": "healthy",
            }, tokens

        if step_id == "dedup":
            return {
                "dedup_applied": False,
                "duplicates_found": 0,
            }, tokens

        if step_id == "format":
            gen_step = step_results.get("generate")
            raw_response = ""
            if gen_step and gen_step.output:
                raw_response = gen_step.output.get(
                    "response",
                    "",
                )
            return {
                "formatted_response": raw_response,
                "format_type": "text",
            }, tokens

        return {"raw_output": True}, tokens

    # ── Checkpoint / State Query Methods ────────────────────────

    async def get_workflow_state(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the current checkpointed workflow state for a thread.

        Uses the checkpointer's ``aget_tuple`` to load the latest
        checkpoint for the given ``thread_id``.  Returns ``None`` if
        no checkpoint exists or the checkpointer is not configured.

        Args:
            thread_id: The conversation / ticket thread identifier
                (same value used during ``execute()``).

        Returns:
            Dictionary with ``values`` (current state) and ``metadata``,
            or ``None`` if no checkpoint is available.
        """
        try:
            if self._checkpointer is None:
                logger.debug(
                    "checkpoint_get_state_no_checkpointer",
                    thread_id=thread_id,
                )
                return None

            config: Dict[str, Any] = {
                "configurable": {"thread_id": thread_id},
            }

            # MemorySaver exposes aget_tuple directly.
            if hasattr(self._checkpointer, "aget_tuple"):
                checkpoint_tuple = await self._checkpointer.aget_tuple(config)
                if checkpoint_tuple is None:
                    logger.info(
                        "checkpoint_get_state_no_checkpoint",
                        thread_id=thread_id,
                    )
                    return None

                state_values = checkpoint_tuple.values
                metadata = checkpoint_tuple.metadata or {}
                logger.info(
                    "checkpoint_state_loaded",
                    thread_id=thread_id,
                    checkpoint_ns=metadata.get("source", "unknown"),
                )
                return {
                    "values": state_values,
                    "metadata": metadata,
                    "thread_id": thread_id,
                }

            logger.warning(
                "checkpoint_get_state_unsupported_checkpointer",
                checkpointer_type=type(self._checkpointer).__name__,
            )
            return None
        except Exception as exc:
            logger.warning(
                "checkpoint_get_state_error",
                thread_id=thread_id,
                error=str(exc),
            )
            return None

    async def resume_workflow(
        self,
        thread_id: str,
        state_updates: Optional[Dict[str, Any]] = None,
    ) -> Optional[WorkflowResult]:
        """Resume a previously checkpointed workflow from its last state.

        Loads the latest checkpoint for ``thread_id``, optionally merges
        ``state_updates`` into the loaded state, and continues graph
        execution from the last completed node.

        This is useful for:
          - Recovering from a mid-pipeline failure
          - Injecting new context (e.g. updated knowledge) after a pause
          - Human-in-the-loop approval patterns

        Args:
            thread_id: The conversation / ticket thread identifier.
            state_updates: Optional dict of state fields to merge into
                the loaded checkpoint before resuming.

        Returns:
            WorkflowResult if the graph was successfully resumed, or
            ``None`` if no checkpoint exists or resumption failed.
        """
        try:
            if self._checkpointer is None or self._graph is None:
                logger.info(
                    "checkpoint_resume_unavailable",
                    thread_id=thread_id,
                    has_checkpointer=self._checkpointer is not None,
                    has_graph=self._graph is not None,
                )
                return None

            config: Dict[str, Any] = {
                "configurable": {"thread_id": thread_id},
            }

            # Load the existing checkpoint
            checkpoint_state = await self.get_workflow_state(thread_id)
            if checkpoint_state is None:
                logger.info(
                    "checkpoint_resume_no_state",
                    thread_id=thread_id,
                )
                return None

            # Merge state updates if provided
            current_values = checkpoint_state.get("values", {})
            if state_updates:
                merged = dict(current_values)
                for key, value in state_updates.items():
                    # Merge step_outputs dicts, replace everything else
                    if (
                        key == "step_outputs"
                        and isinstance(merged.get(key), dict)
                        and isinstance(value, dict)
                    ):
                        merged[key] = {**merged[key], **value}
                    else:
                        merged[key] = value
                input_state = merged
            else:
                input_state = None  # None means "resume from last checkpoint"

            workflow_id = f"resume-{str(uuid.uuid4())[:8]}"
            pipeline_start = time.monotonic()

            logger.info(
                "checkpoint_resuming_workflow",
                thread_id=thread_id,
                workflow_id=workflow_id,
                has_updates=state_updates is not None,
            )

            # Resume: pass None as input to continue from checkpoint,
            # or the merged state if updates were provided.
            if input_state is not None:
                final_state = await self._graph.ainvoke(input_state, config)
            else:
                final_state = await self._graph.ainvoke(None, config)

            # Parse results (same logic as _execute_via_langgraph)
            step_outputs = final_state.get("step_outputs", {})
            step_results: Dict[str, WorkflowStepResult] = {}
            steps_completed: List[str] = []
            total_tokens = final_state.get("total_tokens", 0)
            final_response = final_state.get("final_response", "")
            errors = final_state.get("errors", [])
            overall_status = "success"

            for step_id, output in step_outputs.items():
                step_results[step_id] = WorkflowStepResult(
                    step_id=step_id,
                    status=output.get("status", "unknown"),
                    tokens_used=output.get("tokens_used", 0),
                    duration_ms=output.get("duration_ms", 0.0),
                    error=output.get("error"),
                    output=output.get("output", {}),
                )
                if output.get("status") == "success":
                    steps_completed.append(step_id)
                elif output.get("status") in ("error", "timeout"):
                    overall_status = "partial"

            if errors:
                overall_status = "partial"

            total_duration_ms = round((time.monotonic() - pipeline_start) * 1000, 2)

            logger.info(
                "checkpoint_resume_completed",
                thread_id=thread_id,
                workflow_id=workflow_id,
                status=overall_status,
                steps_completed=len(steps_completed),
                duration_ms=total_duration_ms,
            )

            return WorkflowResult(
                workflow_id=workflow_id,
                variant_type=self._config.variant_type,
                status=overall_status,
                steps_completed=steps_completed,
                step_results=step_results,
                final_response=final_response,
                total_tokens_used=total_tokens,
                total_duration_ms=total_duration_ms,
            )

        except Exception as exc:
            logger.warning(
                "checkpoint_resume_error",
                thread_id=thread_id,
                error=str(exc),
            )
            return None

    # ── Query Methods ──────────────────────────────────────────

    def get_step(
        self,
        step_id: str,
    ) -> Optional[WorkflowStep]:
        """Look up a step by its ID. Returns None if not found."""
        try:
            for step in self._steps:
                if step.step_id == step_id:
                    return step
            return None
        except Exception as exc:
            logger.warning(
                "workflow_get_step_failed",
                step_id=step_id,
                error=str(exc),
                company_id=self._config.company_id,
            )
            return None

    def get_pipeline_topology(
        self,
        company_id: str = "",
    ) -> Dict[str, Any]:
        """Return the graph structure as a serialisable dict.

        Includes all steps with their types, order, and connections.
        """
        try:
            if not self._steps:
                self.build_graph()

            steps_list = []
            for i, step in enumerate(self._steps):
                steps_list.append(
                    {
                        "index": i,
                        "step_id": step.step_id,
                        "step_name": step.step_name,
                        "step_type": step.step_type,
                        "estimated_tokens": step.estimated_tokens,
                        "timeout_seconds": step.timeout_seconds,
                        "enabled": step.enabled,
                        "next": (
                            self._steps[i + 1].step_id
                            if i + 1 < len(self._steps)
                            else None
                        ),
                        "prev": (self._steps[i - 1].step_id if i > 0 else None),
                    }
                )

            return {
                "variant_type": self._config.variant_type,
                "total_steps": len(self._steps),
                "steps": steps_list,
                "total_estimated_tokens": sum(s.estimated_tokens for s in self._steps),
                "max_pipeline_time_seconds": (self._config.max_pipeline_time_seconds),
                "langgraph_available": self._langgraph_available,
            }
        except Exception as exc:
            logger.warning(
                "workflow_get_topology_failed",
                error=str(exc),
                company_id=company_id,
            )
            return {
                "variant_type": self._config.variant_type,
                "total_steps": 0,
                "steps": [],
                "error": str(exc),
            }

    def get_config(self) -> WorkflowConfig:
        """Return the current workflow configuration."""
        return self._config

    def reset(self) -> None:
        """Reset the workflow engine state. For testing."""
        try:
            self._graph = None
            self._steps = []
            self._langgraph_available = None
            # Re-initialise a fresh checkpointer (clears MemorySaver state).
            self._init_checkpointer()
            logger.info("workflow_engine_reset")
        except Exception as exc:
            logger.warning(
                "workflow_reset_failed",
                error=str(exc),
            )
