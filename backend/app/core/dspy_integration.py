"""
DSPy Framework Integration (F-061)

Provides DSPy module wrappers for PARWA techniques with:
- Signature definitions for common AI tasks
- Optimizer integration (BootstrapFewShot, MIPROv2)
- Metric definitions for technique quality
- DSPy adapter bridging ConversationState with DSPy modules
- Fallback mechanism (graceful degradation when DSPy unavailable)
- Per-tenant configuration

DSPy may not be installed. This module uses try/except ImportError
to gracefully degrade to stub implementations.

Parent: Week 10 Day 3
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("dspy_integration")

# Try importing DSPy — gracefully handle if not installed
try:
    import dspy

    _DSPY_AVAILABLE = True
except ImportError:
    dspy = None  # type: ignore[assignment]
    _DSPY_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class DSPyConfig:
    """Per-tenant DSPy configuration."""
    enabled: bool = True
    model_name: str = "gpt-4o-mini"
    max_tokens: int = 500
    temperature: float = 0.3
    optimizer: str = "BootstrapFewShot"
    num_threads: int = 4
    metric_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "relevance": 0.4,
            "accuracy": 0.3,
            "conciseness": 0.2,
            "safety": 0.1,
        }
    )


@dataclass
class ExecutionMetric:
    """A single DSPy execution metric."""
    task_type: str
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None
    fallback_used: bool = False


@dataclass
class SignatureDefinition:
    """Definition of a DSPy signature."""
    name: str
    inputs: List[str]
    outputs: List[str]
    docstring: str = ""


# ══════════════════════════════════════════════════════════════════
# PREDEFINED SIGNATURES
# ══════════════════════════════════════════════════════════════════

PREDEFINED_SIGNATURES: Dict[str, SignatureDefinition] = {
    "classify": SignatureDefinition(
        name="ClassifyIntent",
        inputs=["customer_query", "context"],
        outputs=["intent", "confidence", "reasoning"],
        docstring=(
            "Classify customer intent from query and context."
        ),
    ),
    "respond": SignatureDefinition(
        name="GenerateResponse",
        inputs=[
            "customer_query", "intent", "context",
            "gsd_state", "knowledge",
        ],
        outputs=["response", "confidence", "follow_up_needed"],
        docstring="Generate a support response.",
    ),
    "summarize": SignatureDefinition(
        name="SummarizeConversation",
        inputs=["conversation_history", "max_length"],
        outputs=["summary", "key_points", "sentiment"],
        docstring="Summarize a support conversation.",
    ),
    "escalate": SignatureDefinition(
        name="EscalationDecision",
        inputs=[
            "customer_query", "frustration_score",
            "intent", "conversation_history",
        ],
        outputs=[
            "should_escalate", "escalation_reason",
            "priority",
        ],
        docstring="Decide if a ticket should be escalated.",
    ),
}


# ══════════════════════════════════════════════════════════════════
# STUB MODULE (when DSPy is not installed)
# ══════════════════════════════════════════════════════════════════


class StubModule:
    """Stub DSPy module for fallback when DSPy is not installed."""

    def __init__(self, task_type: str = "unknown") -> None:
        self.task_type = task_type

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return StubPrediction(task_type=self.task_type)


@dataclass
class StubPrediction:
    """Stub prediction output."""
    task_type: str = "unknown"
    response: str = ""
    confidence: float = 0.0


class StubOptimizer:
    """Stub optimizer for fallback."""

    def compile(
        self,
        module: Any,
        trainset: Any = None,
        metric: Any = None,
    ) -> Any:
        return module


# ══════════════════════════════════════════════════════════════════
# DSPy INTEGRATION
# ══════════════════════════════════════════════════════════════════


class DSPyIntegration:
    """DSPy framework integration for PARWA.

    Bridges PARWA's ConversationState with DSPy modules for
    optimized AI-driven tasks.

    When DSPy is not installed, all operations fall back to
    stub implementations that return sensible defaults.

    Usage::

        dspy_int = DSPyIntegration()
        dspy_int.configure("co_123", {"model_name": "gpt-4o"})

        sig = dspy_int.define_signature("classify")
        module = dspy_int.create_module("classify")
        result = dspy_int.execute(module, {"customer_query": "..."})
    """

    def __init__(self) -> None:
        self._tenant_configs: Dict[str, DSPyConfig] = {}
        self._metrics: List[ExecutionMetric] = []
        self._max_metrics = 1000

    # ── Availability ───────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """Check if DSPy is installed and available.

        Returns:
            True if DSPy can be imported, False otherwise.
        """
        return _DSPY_AVAILABLE

    # ── Signature Definitions ──────────────────────────────────

    def define_signature(
        self,
        task_type: str,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
    ) -> Any:
        """Define or retrieve a DSPy signature for a task type.

        Args:
            task_type: Task identifier (e.g. 'classify', 'respond').
            inputs: Optional override of input fields.
            outputs: Optional override of output fields.

        Returns:
            DSPy Signature class or StubModule if unavailable.
        """
        # Check predefined
        predefined = PREDEFINED_SIGNATURES.get(task_type)
        if predefined:
            inp = inputs or predefined.inputs
            out = outputs or predefined.outputs
        else:
            inp = inputs or ["input"]
            out = outputs or ["output"]

        if not _DSPY_AVAILABLE:
            logger.debug(
                "dspy_stub_signature",
                task_type=task_type,
            )
            return type(
                f"StubSignature_{task_type}",
                (),
                {"inputs": inp, "outputs": out},
            )

        try:
            sig = dspy.Signature(
                ", ".join(inp), ", ".join(out)
            )
            return sig
        except Exception as exc:
            logger.warning(
                "dspy_signature_error",
                task_type=task_type,
                error=str(exc),
            )
            return type(
                f"StubSignature_{task_type}",
                (),
                {"inputs": inp, "outputs": out},
            )

    # ── Module Creation ────────────────────────────────────────

    def create_module(
        self,
        task_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create a DSPy module for a task type.

        Args:
            task_type: Task identifier.
            config: Optional module configuration.

        Returns:
            DSPy module instance or StubModule.
        """
        if not _DSPY_AVAILABLE:
            return StubModule(task_type=task_type)

        cfg = config or {}
        sig_def = PREDEFINED_SIGNATURES.get(task_type)

        try:
            if sig_def:
                signature = dspy.Signature(
                    ", ".join(sig_def.inputs),
                    ", ".join(sig_def.outputs),
                )
            else:
                signature = dspy.Signature("input", "output")

            module = dspy.Predict(signature)

            if "num_candidates" in cfg:
                module = dspy.ChainOfThought(signature)
                module.max_generated_tokens = cfg.get(
                    "max_tokens", 500
                )

            return module
        except Exception as exc:
            logger.warning(
                "dspy_module_create_error",
                task_type=task_type,
                error=str(exc),
            )
            return StubModule(task_type=task_type)

    # ── Optimization ───────────────────────────────────────────

    def optimize(
        self,
        module: Any,
        trainset: Any = None,
        metric: Optional[Callable] = None,
        optimizer_name: str = "BootstrapFewShot",
    ) -> Any:
        """Optimize a DSPy module with an optimizer.

        Args:
            module: DSPy module to optimize.
            trainset: Training examples.
            metric: Evaluation metric callable.
            optimizer_name: Optimizer to use.

        Returns:
            Optimized module or original if unavailable.
        """
        if not _DSPY_AVAILABLE:
            logger.info(
                "dspy_stub_optimize",
                optimizer=optimizer_name,
            )
            return module

        try:
            if optimizer_name == "MIPROv2" and hasattr(
                dspy, "MIPROv2"
            ):
                opt = dspy.MIPROv2(
                    metric=metric or self._default_metric,
                    num_threads=4,
                )
            else:
                opt = dspy.BootstrapFewShot(
                    metric=metric or self._default_metric,
                )

            if trainset is None:
                trainset = []

            optimized = opt.compile(module, trainset=trainset)
            return optimized
        except Exception as exc:
            logger.warning(
                "dspy_optimize_error",
                optimizer=optimizer_name,
                error=str(exc),
            )
            return module

    @staticmethod
    def _default_metric(example: Any, pred: Any) -> float:
        """Default metric for DSPy optimization.

        Returns a score between 0.0 and 1.0.
        """
        return 0.5

    # ── Execution ──────────────────────────────────────────────

    def execute(
        self,
        module: Any,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a DSPy module with given inputs.

        Falls back to stub execution if DSPy is unavailable.

        Args:
            module: DSPy module or StubModule.
            inputs: Input key-value pairs.

        Returns:
            Dictionary with output key-value pairs.
        """
        start_time = time.time()
        success = True
        fallback_used = False
        error = None

        try:
            if isinstance(module, StubModule):
                fallback_used = True
                return self._stub_execute(module, inputs)

            if not _DSPY_AVAILABLE:
                fallback_used = True
                stub = StubModule(task_type=getattr(module, 'task_type', 'unknown'))
                return self._stub_execute(stub, inputs)

            # DSPy execution
            prediction = module(**inputs)
            result = {}
            if hasattr(prediction, "__dict__"):
                for k, v in prediction.__dict__.items():
                    if not k.startswith("_"):
                        result[k] = v
            else:
                result = {"output": str(prediction)}

            return result
        except Exception as exc:
            success = False
            error = str(exc)
            logger.warning(
                "dspy_execute_error",
                error=error,
                fallback=True,
            )
            # Fallback to stub
            fallback_used = True
            return self._stub_execute(
                StubModule(), inputs
            )
        finally:
            latency = (time.time() - start_time) * 1000
            self._record_metric(
                ExecutionMetric(
                    task_type=getattr(
                        module, "task_type", "unknown"
                    ),
                    latency_ms=latency,
                    success=success,
                    error=error,
                    fallback_used=fallback_used,
                )
            )

    @staticmethod
    def _stub_execute(
        module: Any,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a stub module with sensible defaults."""
        query = inputs.get("customer_query", inputs.get("input", ""))
        query_len = len(str(query))

        return {
            "response": (
                f"[Fallback] Processing: "
                f"{str(query)[:100]}..."
                if query_len > 100
                else f"[Fallback] Processing: {query}"
            ),
            "confidence": 0.5,
            "reasoning": "Stub fallback - DSPy not available",
            "intent": "general",
            "follow_up_needed": False,
            "should_escalate": False,
            "summary": str(query)[:200] if query else "",
            "key_points": [],
            "sentiment": "neutral",
            "escalation_reason": "",
            "priority": "normal",
        }

    # ── PARWA Bridge ───────────────────────────────────────────

    def bridge_to_parwa(
        self,
        dspy_output: Dict[str, Any],
        conversation_state: Any,
    ) -> Dict[str, Any]:
        """Bridge DSPy output back to PARWA ConversationState.

        Maps DSPy output fields to ConversationState attributes.

        Args:
            dspy_output: Output from DSPy module execution.
            conversation_state: Current ConversationState.

        Returns:
            Dictionary of ConversationState updates to apply.
        """
        updates: Dict[str, Any] = {}

        if "response" in dspy_output:
            updates["final_response"] = dspy_output["response"]
            updates.setdefault("response_parts", []).append(
                dspy_output["response"]
            )

        if "confidence" in dspy_output:
            try:
                conf = float(dspy_output["confidence"])
                updates["signals_confidence"] = conf
            except (ValueError, TypeError):
                pass

        if "intent" in dspy_output:
            updates["signals_intent"] = dspy_output["intent"]

        if "follow_up_needed" in dspy_output:
            updates["follow_up_needed"] = bool(
                dspy_output["follow_up_needed"]
            )

        if "should_escalate" in dspy_output:
            updates["should_escalate"] = bool(
                dspy_output["should_escalate"]
            )

        if "summary" in dspy_output:
            updates["summary"] = dspy_output["summary"]

        return updates

    def bridge_from_parwa(
        self,
        conversation_state: Any,
    ) -> Dict[str, Any]:
        """Bridge PARWA ConversationState to DSPy inputs.

        Extracts relevant fields from ConversationState for
        DSPy module execution.

        Args:
            conversation_state: Current ConversationState.

        Returns:
            Dictionary of DSPy input key-value pairs.
        """
        inputs: Dict[str, Any] = {}

        if hasattr(conversation_state, "query"):
            inputs["customer_query"] = conversation_state.query
            inputs["input"] = conversation_state.query

        if hasattr(conversation_state, "signals"):
            sig = conversation_state.signals
            inputs["context"] = getattr(sig, "intent_type", "general")
            inputs["frustration_score"] = getattr(
                sig, "frustration_score", 0.0
            )
            inputs["sentiment_score"] = getattr(
                sig, "sentiment_score", 0.7
            )
            inputs["intent"] = getattr(
                sig, "intent_type", "general"
            )
            inputs["query_complexity"] = getattr(
                sig, "query_complexity", 0.5
            )

        if hasattr(conversation_state, "gsd_state"):
            gs = conversation_state.gsd_state
            inputs["gsd_state"] = (
                gs.value if hasattr(gs, "value") else str(gs)
            )

        if hasattr(conversation_state, "gsd_history"):
            inputs["conversation_history"] = [
                str(s) for s in conversation_state.gsd_history
            ]

        if hasattr(conversation_state, "technique_results"):
            inputs["knowledge"] = str(
                conversation_state.technique_results
            )

        return inputs

    # ── Metrics ────────────────────────────────────────────────

    def _record_metric(self, metric: ExecutionMetric) -> None:
        """Record an execution metric."""
        self._metrics.append(metric)
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get DSPy execution metrics summary.

        Returns:
            Dictionary with execution statistics.
        """
        if not self._metrics:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "fallback_rate": 0.0,
                "error_rate": 0.0,
                "by_task_type": {},
            }

        total = len(self._metrics)
        successes = sum(1 for m in self._metrics if m.success)
        fallbacks = sum(
            1 for m in self._metrics if m.fallback_used
        )
        errors = sum(1 for m in self._metrics if m.error)
        avg_latency = sum(
            m.latency_ms for m in self._metrics
        ) / total

        by_task: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "successes": 0,
                "fallbacks": 0,
                "avg_latency_ms": 0.0,
            }
        )
        for m in self._metrics:
            task = by_task[m.task_type]
            task["count"] += 1
            task["successes"] += int(m.success)
            task["fallbacks"] += int(m.fallback_used)
            task["avg_latency_ms"] = (
                (
                    task["avg_latency_ms"]
                    * (task["count"] - 1)
                    + m.latency_ms
                )
                / task["count"]
            )

        return {
            "total_executions": total,
            "success_rate": round(successes / total * 100, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "fallback_rate": round(fallbacks / total * 100, 2),
            "error_rate": round(errors / total * 100, 2),
            "by_task_type": dict(by_task),
        }

    # ── Configuration ──────────────────────────────────────────

    def configure(
        self,
        company_id: str,
        config_dict: Dict[str, Any],
    ) -> DSPyConfig:
        """Set per-tenant DSPy configuration.

        Args:
            company_id: Tenant identifier.
            config_dict: Configuration values.

        Returns:
            The applied DSPyConfig.
        """
        config = DSPyConfig(
            enabled=config_dict.get("enabled", True),
            model_name=config_dict.get("model_name", "gpt-4o-mini"),
            max_tokens=config_dict.get("max_tokens", 500),
            temperature=config_dict.get("temperature", 0.3),
            optimizer=config_dict.get(
                "optimizer", "BootstrapFewShot"
            ),
            num_threads=config_dict.get("num_threads", 4),
            metric_weights=config_dict.get(
                "metric_weights",
                DSPyConfig().metric_weights,
            ),
        )
        self._tenant_configs[company_id] = config
        logger.info(
            "dspy_configured",
            company_id=company_id,
            model=config.model_name,
            enabled=config.enabled,
        )
        return config

    def get_config(self, company_id: str) -> DSPyConfig:
        """Get DSPy configuration for a tenant.

        Args:
            company_id: Tenant identifier.

        Returns:
            DSPyConfig for the tenant.
        """
        return self._tenant_configs.get(
            company_id, DSPyConfig()
        )

    def reset_metrics(self) -> None:
        """Clear all recorded metrics (for testing)."""
        self._metrics.clear()
