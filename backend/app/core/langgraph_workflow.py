"""
F-200: LangGraph Workflow Engine (Week 10 Day 12)

Orchestrates the AI response generation pipeline by building a
StateGraph with nodes for each pipeline step. Three variant tiers:

  - mini_parwa (L1):  3-step simplified pipeline
  - parwa      (L2):  6-step standard pipeline
  - parwa_high (L3):  9-step full pipeline

Each step is a node in the graph. The engine executes steps
sequentially, tracks per-step results, and handles timeouts.

BC-001: All public methods take company_id as the first parameter.
BC-008: Every public method is wrapped in try/except; never crashes.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("langgraph_workflow")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

_WORKFLOW_TIMEOUT_SECONDS: float = 30.0
_DEFAULT_MAX_TOKENS: int = 1500

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
    "parwa_high": {
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
        self, config: Optional[WorkflowConfig] = None,
    ) -> None:
        self._config = config or WorkflowConfig()
        self._graph: Any = None  # lazy-built StateGraph
        self._steps: List[WorkflowStep] = []
        self._langgraph_available: Optional[bool] = None

        logger.info(
            "workflow_engine_initialized",
            variant_type=self._config.variant_type,
            company_id=self._config.company_id,
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
        sequential edges. Falls back gracefully when langgraph is
        not installed (BC-008).
        """
        try:
            from langgraph.graph import StateGraph, END
            from typing import TypedDict, Annotated
            import operator

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

            builder = StateGraph(WorkflowState)

            # Register a node for each step in the pipeline
            step_ids = [s.step_id for s in self._steps]
            for step_id in step_ids:
                async def _node_fn(state: dict, _sid=step_id) -> dict:
                    """Delegate to the real step executor."""
                    try:
                        # Find the WorkflowStep definition for this step_id
                        wf_step = next(
                            (s for s in self._steps if s.step_id == _sid), None,
                        )
                        if wf_step is None:
                            return {
                                "step_outputs": {
                                    _sid: {"status": "error", "error": "Unknown step"},
                                },
                                "errors": state.get("errors", []) + [f"Unknown step: {_sid}"],
                            }

                        step_result = await self._execute_step(
                            company_id=state.get("company_id", self._config.company_id),
                            wf_step=wf_step,
                            query=state.get("query", ""),
                            context=state.get("context", {}),
                            step_results={},  # Will be populated from state.step_outputs
                        )

                        return {
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
                                if _sid == "generate" and step_result.status == "success"
                                else state.get("final_response", "")
                            ),
                            "total_tokens": (
                                state.get("total_tokens", 0) + step_result.tokens_used
                            ),
                            "errors": (
                                state.get("errors", [])
                                + [step_result.error] if step_result.error
                                else state.get("errors", [])
                            ),
                        }
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

            # Wire edges sequentially
            for i in range(len(step_ids) - 1):
                builder.add_edge(step_ids[i], step_ids[i + 1])
            # Last step → END
            if step_ids:
                builder.add_edge(step_ids[-1], END)

            self._graph = builder.compile()
            self._langgraph_available = True
            logger.info(
                "langgraph_stategraph_built",
                company_id=self._config.company_id,
                variant_type=self._config.variant_type,
                node_count=len(step_ids),
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
        self, variant_type: str,
    ) -> List[WorkflowStep]:
        """Build the step list for a given variant."""
        builders = {
            "mini_parwa": self._build_mini_parwa_pipeline,
            "parwa": self._build_parwa_pipeline,
            "parwa_high": self._build_parwa_high_pipeline,
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
                "estimated_tokens", 0,
            ),
            timeout_seconds=definition.get(
                "timeout_seconds", 5.0,
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

    def _build_parwa_high_pipeline(self) -> List[WorkflowStep]:
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
                variant, VARIANT_PIPELINE_CONFIG["parwa"],
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
                step_elapsed_ms = (
                    (time.monotonic() - step_start) * 1000
                )
                step_result.duration_ms = round(step_elapsed_ms, 2)

                step_results[wf_step.step_id] = step_result
                total_tokens += step_result.tokens_used

                if step_result.status == "success":
                    steps_completed.append(wf_step.step_id)
                    # Capture special outputs
                    if wf_step.step_id == "context_compress":
                        compression_applied = step_result.output.get(
                            "compressed", False,
                        )
                    if wf_step.step_id == "context_health":
                        health_score = step_result.output.get(
                            "health_score", 1.0,
                        )
                    if wf_step.step_id == "generate":
                        final_response = step_result.output.get(
                            "response", "",
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

            total_duration_ms = (
                (time.monotonic() - pipeline_start) * 1000
            )

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
            total_duration_ms = (
                (time.monotonic() - pipeline_start) * 1000
            )
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
                    step_id, query, context, step_results,
                )
            elif wf_step.step_type == "core":
                output, tokens = self._simulate_core_step(
                    step_id, query, context, step_results,
                )
            else:
                output, tokens = self._simulate_postprocessing(
                    step_id, query, context, step_results,
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
        **kwargs: Any,
    ) -> Optional[WorkflowResult]:
        """Execute the pipeline using the compiled LangGraph StateGraph.

        This is the preferred execution path when langgraph is available,
        as it leverages the graph's built-in state management and error
        handling. Falls back to sequential execution if graph invocation
        fails (BC-008).
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
            }

            # Invoke the compiled graph
            config = {"configurable": {"workflow_id": workflow_id}}
            final_state = await self._graph.ainvoke(initial_state, config)

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
                company_id, query, context, step_results,
            )
        if step_id == "extract_signals":
            return await self._real_extract_signals(
                company_id, query, context, step_results,
            )
        if step_id == "technique_select":
            return await self._real_technique_select(
                company_id, query, context, step_results,
            )
        if step_id == "context_compress":
            return await self._real_context_compress(
                company_id, query, context, step_results,
            )
        if step_id == "generate":
            return await self._real_generate(
                company_id, query, context, step_results,
            )
        if step_id == "quality_gate":
            return await self._real_quality_gate(
                company_id, query, context, step_results,
            )
        if step_id == "context_health":
            return await self._real_context_health(
                company_id, query, context, step_results,
            )
        if step_id == "dedup":
            return self._real_dedup(
                company_id, query, context, step_results,
            )
        if step_id == "format":
            return self._real_format(
                company_id, query, context, step_results,
            )

        # Unknown step — let the caller fall back to simulation
        raise NotImplementedError(
            f"No real handler for step '{step_id}'"
        )

    # ── Individual real step handlers ────────────────────────

    async def _real_classify(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use ClassificationEngine for real intent classification."""
        from app.core.classification_engine import ClassificationEngine

        engine = ClassificationEngine()
        intent_result = await engine.classify(
            text=query,
            company_id=company_id,
            variant_type=self._config.variant_type,
            use_ai=True,
        )
        return {
            "intent": intent_result.primary_intent,
            "confidence": intent_result.confidence,
            "secondary_intents": intent_result.secondary_intents,
            "method": "ai",
        }, intent_result.tokens_used or 50

    async def _real_extract_signals(
        self,
        company_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Use SignalExtractor for real signal extraction."""
        from app.core.signal_extraction import (
            SignalExtractor,
            SignalExtractionRequest,
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
        """Use TechniqueRouter for real technique selection."""
        from app.core.technique_router import (
            TechniqueRouter,
            QuerySignals,
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

        signals = QuerySignals(
            query_complexity=extract_out.get("complexity", 0.5),
            confidence_score=classify_out.get("confidence", 0.8),
            sentiment_score=extract_out.get("sentiment", 0.7),
            intent_type=classify_out.get("intent", "general"),
            customer_tier=extract_out.get("customer_tier", "free"),
            monetary_value=extract_out.get("monetary_value", 0.0),
            turn_count=extract_out.get("turn_count", 0),
            previous_response_status=extract_out.get(
                "previous_response_status", "none",
            ),
            reasoning_loop_detected=extract_out.get(
                "reasoning_loop_detected", False,
            ),
            resolution_path_count=extract_out.get(
                "resolution_path_count", 1,
            ),
        )

        router = TechniqueRouter()
        result = router.route(signals)

        activated = [
            ta.technique_id.value
            for ta in result.activated_techniques
        ]
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
            ContextCompressor,
            CompressionInput,
        )

        compressor = ContextCompressor()

        # Gather context content to compress
        raw_context = context.get("knowledge_context") or context.get("conversation_history") or []
        if isinstance(raw_context, str):
            content_chunks = [raw_context]
        elif isinstance(raw_context, list):
            content_chunks = [
                chunk if isinstance(chunk, str) else str(chunk)
                for chunk in raw_context
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
            SmartRouter,
            AtomicStepType,
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

        # Build messages payload
        system_prompt = context.get("system_prompt", "") or "You are a helpful customer support assistant."
        knowledge_ctx = context.get("knowledge_context", "")
        if knowledge_ctx and isinstance(knowledge_ctx, (list, str)):
            if isinstance(knowledge_ctx, list):
                knowledge_ctx = "\n".join(
                    str(k) for k in knowledge_ctx
                )
            system_prompt += f"\n\nRelevant context:\n{knowledge_ctx}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

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
            unique_sentences = list(dict.fromkeys(
                s.strip() for s in response.split(".") if s.strip()
            ))
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
            step_id, {},
        ).get("estimated_tokens", 50)

        if step_id == "classify":
            # Classify intent from query length and content
            intent = "general_inquiry"
            q_lower = query.lower()
            if any(
                w in q_lower
                for w in ["refund", "cancel", "return", "money"]
            ):
                intent = "refund_request"
            elif any(
                w in q_lower
                for w in ["order", "ship", "track", "delivery"]
            ):
                intent = "order_status"
            elif any(
                w in q_lower
                for w in ["error", "bug", "broken", "not work"]
            ):
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
                if prev_classify else "general"
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
                    "context_tokens", 500,
                ),
                "compressed_tokens": context.get(
                    "context_tokens", 500,
                ) * 0.7,
            }, tokens

        return {"raw_output": True}, tokens

    def _simulate_core_step(
        self,
        step_id: str,
        query: str,
        context: Dict[str, Any],
        step_results: Dict[str, WorkflowStepResult],
    ) -> Tuple[Dict[str, Any], int]:
        """Simulate a core processing step output."""
        tokens = WORKFLOW_STEP_DEFINITIONS.get(
            step_id, {},
        ).get("estimated_tokens", 500)

        if step_id == "generate":
            technique = "standard_response"
            tech_step = step_results.get("technique_select")
            if tech_step and tech_step.output:
                technique = tech_step.output.get(
                    "technique", technique,
                )

            response = (
                f"Thank you for your message. "
                f"Regarding your query about '{query[:50]}', "
                f"I'd be happy to help. "
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
            step_id, {},
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
                    "response", "",
                )
            return {
                "formatted_response": raw_response,
                "format_type": "text",
            }, tokens

        return {"raw_output": True}, tokens

    # ── Query Methods ──────────────────────────────────────────

    def get_step(
        self, step_id: str,
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
        self, company_id: str = "",
    ) -> Dict[str, Any]:
        """Return the graph structure as a serialisable dict.

        Includes all steps with their types, order, and connections.
        """
        try:
            if not self._steps:
                self.build_graph()

            steps_list = []
            for i, step in enumerate(self._steps):
                steps_list.append({
                    "index": i,
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "estimated_tokens": step.estimated_tokens,
                    "timeout_seconds": step.timeout_seconds,
                    "enabled": step.enabled,
                    "next": (
                        self._steps[i + 1].step_id
                        if i + 1 < len(self._steps) else None
                    ),
                    "prev": (
                        self._steps[i - 1].step_id
                        if i > 0 else None
                    ),
                })

            return {
                "variant_type": self._config.variant_type,
                "total_steps": len(self._steps),
                "steps": steps_list,
                "total_estimated_tokens": sum(
                    s.estimated_tokens for s in self._steps
                ),
                "max_pipeline_time_seconds": (
                    self._config.max_pipeline_time_seconds
                ),
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
            logger.info("workflow_engine_reset")
        except Exception as exc:
            logger.warning(
                "workflow_reset_failed",
                error=str(exc),
            )
