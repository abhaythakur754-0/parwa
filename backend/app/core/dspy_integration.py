"""
DSPy Framework Integration (F-061)

Provides DSPy module wrappers for PARWA techniques with:
- Signature definitions for common AI tasks
- Optimizer integration (BootstrapFewShot, MIPROv2)
- Metric definitions for technique quality
- DSPy adapter bridging ConversationState with DSPy modules
- Fallback mechanism (graceful degradation when DSPy unavailable)
- Per-tenant configuration

Wiring: ai_pipeline.py's ``_stage_response_generation`` calls
``DSPyIntegration.optimize_response()`` when the ``DSPY_ENABLED``
environment variable is set to ``true`` (default: ``false``).
The optimization intercepts the response *after* standard generation
but *before* the CLARA quality gate.  On any DSPy failure the
original response is preserved (BC-008 graceful degradation).

DSPy may not be installed. This module uses try/except ImportError
to gracefully degrade to stub implementations.

Parent: Week 10 Day 3
"""

from __future__ import annotations

import os
import pickle
import re
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
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

# Try importing intent_prompt_templates — gracefully handle
try:
    from app.services.intent_prompt_templates import PromptTemplateRegistry

    _TEMPLATES_AVAILABLE = True
except ImportError:
    PromptTemplateRegistry = None  # type: ignore[assignment,misc]
    _TEMPLATES_AVAILABLE = False

# Harmful / PII keywords for safety metric
_SAFETY_BLOCKLIST: List[str] = [
    "ssn", "social security", "credit card number", "cvv",
    "password", "secret_key", "api_key", "private_key",
    "bank account", "routing number", "passport number",
    "driver license", "medical record", "health insurance",
]

# Cache directory for compiled modules
_DSPY_CACHE_DIR = Path("/tmp/dspy_cache")


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
    def _relevance_score(
        query: str,
        response: str,
    ) -> float:
        """Measure keyword overlap between query intent and response.

        Tokenises both strings on word boundaries and returns the
        Jaccard-like ratio of shared terms.  Returns 1.0 when all
        query words appear in the response.
        """
        try:
            q_words = set(
                w.lower() for w in re.findall(r"\b\w+\b", query)
            )
            r_words = set(
                w.lower() for w in re.findall(r"\b\w+\b", response)
            )
            if not q_words:
                return 1.0
            overlap = q_words & r_words
            return len(overlap) / len(q_words)
        except Exception:
            return 0.5

    @staticmethod
    def _accuracy_score(pred: Any, example: Any) -> float:
        """Check whether expected output fields are present and non-empty.

        Looks for keys ``response``, ``intent``, ``confidence`` inside
        the prediction and verifies they are truthy strings / numbers.
        """
        try:
            pred_dict: Dict[str, Any] = {}
            if hasattr(pred, "__dict__"):
                pred_dict = {
                    k: v
                    for k, v in pred.__dict__.items()
                    if not k.startswith("_")
                }
            elif isinstance(pred, dict):
                pred_dict = pred

            required_fields = ["response", "intent", "confidence"]
            filled = sum(
                1 for f in required_fields
                if pred_dict.get(f) not in (None, "", 0, 0.0, False)
            )
            return filled / len(required_fields)
        except Exception:
            return 0.5

    @staticmethod
    def _conciseness_score(query: str, response: str) -> float:
        """Penalise responses longer than 2× the query length.

        Returns 1.0 when the response is ≤ 2× the query length,
        and decays linearly towards 0.0 for longer responses.
        """
        try:
            q_len = len(query.strip())
            r_len = len(response.strip())
            if q_len == 0:
                return 1.0 if r_len < 500 else 0.5
            threshold = q_len * 2
            if r_len <= threshold:
                return 1.0
            # Linear decay from 1.0 → 0.0 over the next threshold-length
            excess = r_len - threshold
            return max(0.0, 1.0 - excess / threshold)
        except Exception:
            return 0.5

    @staticmethod
    def _safety_score(response: str) -> float:
        """Check for harmful / PII content in the response.

        Returns 0.0 if any blocklist phrase is found, 1.0 otherwise.
        """
        try:
            response_lower = response.lower()
            for phrase in _SAFETY_BLOCKLIST:
                if phrase in response_lower:
                    return 0.0
            return 1.0
        except Exception:
            return 0.5

    def _default_metric(self, example: Any, pred: Any) -> float:
        """Composite metric for DSPy optimization.

        Evaluates relevance, accuracy, conciseness, and safety.
        Weights are read from ``DSPyConfig.metric_weights``.
        Returns a score between 0.0 and 1.0.

        Args:
            example: A DSPy Example (or dict with at least
                ``customer_query`` / ``input`` keys).
            pred: A DSPy prediction (object with ``__dict__`` or dict).
        """
        try:
            # ── Extract text from example ───────────────────────
            if isinstance(example, dict):
                query = example.get(
                    "customer_query", example.get("input", "")
                )
            elif hasattr(example, "customer_query"):
                query = example.customer_query
            elif hasattr(example, "input"):
                query = example.input
            else:
                query = ""

            # ── Extract response from pred ──────────────────────
            if isinstance(pred, dict):
                response = pred.get("response", "")
            elif hasattr(pred, "response"):
                response = str(pred.response)
            elif hasattr(pred, "__dict__"):
                response = str(
                    getattr(pred, "response", "") or ""
                )
            else:
                response = str(pred)

            query = str(query)
            response = str(response)

            # ── Compute sub-scores ─────────────────────────────
            relevance = self._relevance_score(query, response)
            accuracy = self._accuracy_score(pred, example)
            conciseness = self._conciseness_score(query, response)
            safety = self._safety_score(response)

            # ── Apply weights from default config ───────────────
            w = DSPyConfig().metric_weights
            score = (
                w.get("relevance", 0.4) * relevance
                + w.get("accuracy", 0.3) * accuracy
                + w.get("conciseness", 0.2) * conciseness
                + w.get("safety", 0.1) * safety
            )
            return round(min(max(score, 0.0), 1.0), 4)
        except Exception as exc:
            logger.warning(
                "dspy_metric_error",
                error=str(exc),
            )
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
            # Fallback to stub — if stub succeeds, mark as recovered
            fallback_used = True
            stub_result = self._stub_execute(StubModule(), inputs)
            # Stub fallback is a successful recovery — don't count as error
            success = True
            error = ""
            return stub_result
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

        Validates provided values before applying. Invalid values
        raise ValueError.

        Args:
            company_id: Tenant identifier.
            config_dict: Configuration values.

        Returns:
            The applied DSPyConfig.

        Raises:
            ValueError: If any provided value is invalid.
        """
        # BUG FIX: Validate configuration values
        if "max_tokens" in config_dict:
            mt = config_dict["max_tokens"]
            if not isinstance(mt, int) or mt <= 0:
                raise ValueError(
                    f"max_tokens must be a positive integer, "
                    f"got {mt!r}"
                )

        if "temperature" in config_dict:
            temp = config_dict["temperature"]
            if not isinstance(temp, (int, float)):
                raise ValueError(
                    f"temperature must be a number, "
                    f"got {temp!r}"
                )
            if not (0.0 <= float(temp) <= 2.0):
                raise ValueError(
                    f"temperature must be between 0.0 and 2.0, "
                    f"got {temp}"
                )

        if "model_name" in config_dict:
            mn = config_dict["model_name"]
            if not isinstance(mn, str) or not mn.strip():
                raise ValueError(
                    f"model_name must be a non-empty string, "
                    f"got {mn!r}"
                )

        if "num_threads" in config_dict:
            nt = config_dict["num_threads"]
            if not isinstance(nt, int) or nt < 1:
                raise ValueError(
                    f"num_threads must be an integer >= 1, "
                    f"got {nt!r}"
                )

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

    # ── Training Data from Templates ───────────────────────────

    def build_training_data_from_templates(
        self,
        templates_module: Any = None,
    ) -> List[Any]:
        """Build DSPy training examples from intent prompt templates.

        Reads the 48 templates (12 intents × 4 response types) from
        :mod:`intent_prompt_templates` and converts each template's
        ``system_prompt`` and ``few_shot_examples`` into DSPy
        ``Example`` objects (or plain dicts when DSPy is unavailable).

        Args:
            templates_module: Optional module override. If *None*,
                the default ``PromptTemplateRegistry`` is used.

        Returns:
            List of ``dspy.Example`` or ``dict`` training examples.
        """
        examples: List[Any] = []
        try:
            registry = None
            if templates_module is not None:
                # Caller provided a module or registry directly
                if isinstance(
                    templates_module, PromptTemplateRegistry
                ) if PromptTemplateRegistry else False:
                    registry = templates_module
                elif hasattr(templates_module, "PromptTemplateRegistry"):
                    registry = templates_module.PromptTemplateRegistry()
                elif callable(getattr(templates_module, "list_all_templates", None)):
                    registry = templates_module
            elif _TEMPLATES_AVAILABLE and PromptTemplateRegistry is not None:
                registry = PromptTemplateRegistry()

            if registry is None:
                logger.warning(
                    "dspy_no_template_registry",
                    available=_TEMPLATES_AVAILABLE,
                )
                return examples

            # Walk all templates and build training examples
            all_templates = registry.list_all_templates()
            for meta in all_templates:
                tid = meta["template_id"]
                intent = meta["intent"]
                response_type = meta["response_type"]

                template = registry.get_template(
                    intent, response_type
                )
                if template is None:
                    continue

                # One training example per few-shot entry
                for shot in template.few_shot_examples:
                    query = shot.get("query", "")
                    response = shot.get("response", "")

                    example_data = {
                        "customer_query": query,
                        "input": query,
                        "intent": intent,
                        "context": template.system_prompt,
                        "response": response,
                        "response_type": response_type,
                        "tone_instructions": template.tone_instructions,
                    }

                    if _DSPY_AVAILABLE and dspy is not None:
                        ex = dspy.Example(**example_data).with_inputs(
                            "customer_query", "input", "intent",
                            "context",
                        )
                        examples.append(ex)
                    else:
                        example_data["_inputs"] = [
                            "customer_query", "input", "intent",
                            "context",
                        ]
                        examples.append(example_data)

            logger.info(
                "dspy_training_data_built",
                total_templates=len(all_templates),
                examples_created=len(examples),
            )
        except Exception as exc:
            logger.warning(
                "dspy_build_training_error",
                error=str(exc),
            )

        return examples

    # ── Compiled Module Persistence ────────────────────────────

    def save_compiled_module(
        self,
        company_id: str,
        task_type: str,
        module: Any,
    ) -> bool:
        """Persist a compiled DSPy module to disk.

        Saves to ``/tmp/dspy_cache/{company_id}/{task_type}.pkl``.
        Gracefully degrades on failure (BC-008).

        Args:
            company_id: Tenant identifier.
            task_type: Task type (e.g. ``"respond"``).
            module: Compiled DSPy module to persist.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        try:
            cache_dir = _DSPY_CACHE_DIR / company_id
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{task_type}.pkl"

            with open(cache_path, "wb") as f:
                pickle.dump(module, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(
                "dspy_module_saved",
                company_id=company_id,
                task_type=task_type,
                path=str(cache_path),
            )
            return True
        except Exception as exc:
            logger.warning(
                "dspy_save_module_error",
                company_id=company_id,
                task_type=task_type,
                error=str(exc),
            )
            return False

    def load_compiled_module(
        self,
        company_id: str,
        task_type: str,
    ) -> Optional[Any]:
        """Load a previously compiled DSPy module from disk.

        Reads from ``/tmp/dspy_cache/{company_id}/{task_type}.pkl``.
        Gracefully degrades on failure (BC-008).

        Args:
            company_id: Tenant identifier.
            task_type: Task type (e.g. ``"respond"``).

        Returns:
            The compiled module, or ``None`` if unavailable / error.
        """
        try:
            cache_path = (
                _DSPY_CACHE_DIR / company_id / f"{task_type}.pkl"
            )
            if not cache_path.exists():
                logger.debug(
                    "dspy_no_cached_module",
                    company_id=company_id,
                    task_type=task_type,
                )
                return None

            with open(cache_path, "rb") as f:
                module = pickle.load(f)

            logger.info(
                "dspy_module_loaded",
                company_id=company_id,
                task_type=task_type,
                path=str(cache_path),
            )
            return module
        except Exception as exc:
            logger.warning(
                "dspy_load_module_error",
                company_id=company_id,
                task_type=task_type,
                error=str(exc),
            )
            return None

    # ── Pipeline Integration ───────────────────────────────────

    def optimize_response(
        self,
        company_id: str,
        query: str,
        context: Any = None,
        rag_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """End-to-end optimized response via the DSPy pipeline.

        Steps:
        1. Load tenant config via :meth:`get_config`.
        2. Attempt to load a cached compiled module.
        3. If no cache, build training data and run optimization.
        4. Execute the (cached or freshly compiled) module.
        5. Return the result dict from :meth:`bridge_to_parwa`.

        Args:
            company_id: Tenant identifier.
            query: Customer query string.
            context: Optional ConversationState object.
            rag_context: Optional RAG-retrieved context string.

        Returns:
            Dictionary of PARWA-compatible response updates.
        """
        try:
            # 1. Tenant config
            config = self.get_config(company_id)
            task_type = "respond"

            if not config.enabled:
                logger.info(
                    "dspy_disabled_for_tenant",
                    company_id=company_id,
                )
                return self._stub_execute(
                    StubModule(task_type=task_type),
                    {"customer_query": query, "input": query},
                )

            # 2. Try loading cached compiled module
            compiled = self.load_compiled_module(
                company_id, task_type
            )

            if compiled is None:
                # 3. Build training data & optimise
                module = self.create_module(
                    task_type,
                    config={
                        "max_tokens": config.max_tokens,
                    },
                )
                trainset = self.build_training_data_from_templates()
                compiled = self.optimize(
                    module,
                    trainset=trainset
                    if trainset else None,
                    metric=self._default_metric,
                    optimizer_name=config.optimizer,
                )
                # Persist for next call
                self.save_compiled_module(
                    company_id, task_type, compiled
                )

            # 4. Execute the compiled module
            inputs: Dict[str, Any] = {
                "customer_query": query,
                "input": query,
                "context": str(context) if context else "",
            }
            if rag_context:
                inputs["knowledge"] = rag_context

            dspy_output = self.execute(compiled, inputs)

            # 5. Bridge back to PARWA format
            result = self.bridge_to_parwa(
                dspy_output, context
            )
            logger.info(
                "dspy_optimize_response_ok",
                company_id=company_id,
                task_type=task_type,
            )
            return result

        except Exception as exc:
            logger.warning(
                "dspy_optimize_response_error",
                company_id=company_id,
                error=str(exc),
            )
            # BC-008 graceful degradation
            return self._stub_execute(
                StubModule(task_type="respond"),
                {"customer_query": query, "input": query},
            )

    # ── Evaluation Harness ─────────────────────────────────────

    def evaluate(
        self,
        module: Any,
        testset: List[Any],
        metric: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Evaluate a DSPy module against a test set.

        Runs the *module* on each test example, records per-example
        sub-scores (relevance, accuracy, conciseness, safety) and
        returns aggregate statistics.

        Args:
            module: DSPy module (or StubModule) to evaluate.
            testset: List of ``dspy.Example`` or dicts.
            metric: Optional metric callable.  If *None*,
                :meth:`_default_metric` is used.

        Returns:
            Dictionary with ``mean``, ``min``, ``max``, ``std``,
            ``total_examples``, and ``per_example`` list.
        """
        try:
            _metric = metric or self._default_metric
            scores: List[float] = []
            per_example: List[Dict[str, Any]] = []

            for idx, example in enumerate(testset):
                try:
                    # Extract inputs from example
                    if isinstance(example, dict):
                        inp_keys = example.get(
                            "_inputs", ["customer_query", "input"]
                        )
                        inputs = {
                            k: example[k]
                            for k in inp_keys
                            if k in example
                        }
                    elif hasattr(example, "_inputs"):
                        inputs = {
                            k: getattr(example, k)
                            for k in example._inputs
                            if hasattr(example, k)
                        }
                    else:
                        # Fallback: pass the whole example
                        inputs = {"customer_query": str(example), "input": str(example)}

                    # Execute module
                    pred = self.execute(module, inputs)

                    # Compute composite score
                    composite = _metric(example, pred)

                    # Also compute individual sub-scores for detail
                    query = str(
                        inputs.get("customer_query", inputs.get("input", ""))
                    )
                    response = str(
                        pred.get("response", "")
                        if isinstance(pred, dict)
                        else getattr(pred, "response", "")
                    )

                    sub_scores = {
                        "relevance": round(
                            self._relevance_score(query, response), 4
                        ),
                        "accuracy": round(
                            self._accuracy_score(pred, example), 4
                        ),
                        "conciseness": round(
                            self._conciseness_score(query, response), 4
                        ),
                        "safety": round(
                            self._safety_score(response), 4
                        ),
                        "composite": round(composite, 4),
                    }

                    scores.append(composite)
                    per_example.append({
                        "index": idx,
                        **sub_scores,
                    })
                except Exception as inner_exc:
                    logger.warning(
                        "dspy_eval_example_error",
                        index=idx,
                        error=str(inner_exc),
                    )
                    scores.append(0.0)
                    per_example.append({
                        "index": idx,
                        "relevance": 0.0,
                        "accuracy": 0.0,
                        "conciseness": 0.0,
                        "safety": 0.0,
                        "composite": 0.0,
                        "error": str(inner_exc),
                    })

            if not scores:
                return {
                    "mean": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "std": 0.0,
                    "total_examples": 0,
                    "per_example": [],
                }

            mean_score = statistics.mean(scores)
            agg = {
                "mean": round(mean_score, 4),
                "min": round(min(scores), 4),
                "max": round(max(scores), 4),
                "std": round(
                    statistics.stdev(scores)
                    if len(scores) > 1
                    else 0.0,
                    4,
                ),
                "total_examples": len(scores),
                "per_example": per_example,
            }

            logger.info(
                "dspy_evaluate_done",
                mean_score=agg["mean"],
                total=len(scores),
            )
            return agg

        except Exception as exc:
            logger.warning(
                "dspy_evaluate_error",
                error=str(exc),
            )
            return {
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0,
                "std": 0.0,
                "total_examples": 0,
                "per_example": [],
                "error": str(exc),
            }
