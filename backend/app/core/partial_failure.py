"""
SG-32: Partial Pipeline Failure Handler (Week 10 Day 4)

Handles graceful degradation when individual pipeline stages fail
but others succeed. Provides fallback responses, retry with reduced
pipeline, error context propagation, and human handoff triggers.

Core Responsibilities:
- Degraded response generation using available signals only
- Fallback response templates per intent (6 intents)
- Automatic retry with reduced pipeline (skip failed stages)
- Error context propagation to downstream stages
- Per-variant degradation thresholds (mini_parwa / parwa / high_parwa)
- Human handoff trigger when too many stages fail

Building Codes: BC-012, BC-007, BC-009, BC-001, BC-008
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("partial_failure")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class PipelineStageStatus(str, Enum):
    """Status of a pipeline stage after execution.

    SUCCESS: Stage completed normally.
    FAILED:  Stage threw an exception or returned an error.
    TIMEOUT: Stage exceeded its time budget.
    SKIPPED: Stage was deliberately bypassed (e.g. reduced pipeline).
    DEGRADED: Stage produced a result but quality is compromised.
    """
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    DEGRADED = "degraded"


class DegradationLevel(str, Enum):
    """Overall degradation level for a pipeline run.

    none:           All stages succeeded.
    degraded:       Some stages failed; fallback response used.
    critical:       Many stages failed; minimal response only.
    human_handoff:  Too many failures; escalate to human agent.
    """
    NONE = "none"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    HUMAN_HANDOFF = "human_handoff"


class PipelineFinalStatus(str, Enum):
    """Final status recorded after a pipeline completes."""
    FULL_SUCCESS = "full_success"
    PARTIAL_SUCCESS = "partial_success"
    DEGRADED_RESPONSE = "degraded_response"
    RETRIED_AND_SUCCEEDED = "retried_and_succeeded"
    RETRIED_AND_DEGRADED = "retried_and_degraded"
    HUMAN_HANDOFF_TRIGGERED = "human_handoff_triggered"
    FULL_FAILURE = "full_failure"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class StageFailure:
    """Record of a single stage failure within a pipeline run.

    Attributes:
        stage_id:     Identifier of the failed pipeline stage
                      (e.g. "signal_extraction", "rag_retrieval").
        error:        Human-readable error message.
        status:       Detailed status (FAILED, TIMEOUT, DEGRADED).
        timestamp:    UTC ISO-8601 timestamp of the failure (BC-012).
        retry_count:  Number of times this stage was retried before
                      recording this failure.
    """
    stage_id: str
    error: str
    status: PipelineStageStatus
    timestamp: str
    retry_count: int = 0


@dataclass
class PipelineContext:
    """Mutable context that flows through pipeline stages.

    Carries all intermediate state, signals, results, and failure
    records across stages. Updated in place as the pipeline progresses.

    Attributes:
        company_id:          Tenant company identifier (BC-001).
        ticket_id:           Support ticket being processed.
        variant:             PARWA variant (mini_parwa, parwa, high_parwa).
        intent:              Detected customer intent (e.g. "refund_request").
        signals:             All extracted signals from upstream stages.
        stage_results:       Outputs from stages that completed successfully.
        failures:            List of stage failures recorded so far.
        error_context:       Propagated error information for downstream
                             stages to adapt their behaviour.
        available_signals:   Names of signals that were successfully
                             extracted (for template matching).
        metadata:            Arbitrary metadata attached by stages.
    """
    company_id: str = ""
    ticket_id: str = ""
    variant: str = "parwa"
    intent: str = "general"
    signals: Dict[str, Any] = field(default_factory=dict)
    stage_results: Dict[str, Any] = field(default_factory=dict)
    failures: List[StageFailure] = field(default_factory=list)
    error_context: Dict[str, Any] = field(default_factory=dict)
    available_signals: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackTemplate:
    """Fallback response template for a specific intent.

    When AI cannot generate a proper response (e.g. due to stage
    failures), a fallback template provides a safe, pre-written reply.

    Attributes:
        intent:             Customer intent this template covers.
        template:           The fallback response text.
        priority:           Lower number = higher priority when multiple
                             templates match the same intent.
        requires_signals:   List of signal names that must be present
                             for this template to be eligible.
    """
    intent: str
    template: str
    priority: int = 10
    requires_signals: List[str] = field(default_factory=list)


@dataclass
class DegradationConfig:
    """Per-variant degradation settings.

    Controls how aggressively the system degrades when pipeline stages
    fail. Each variant has different thresholds reflecting its tier
    capabilities.

    Attributes:
        max_failed_stages:         Number of failed stages before human
                                   handoff is triggered.
        retry_enabled:             Whether automatic retry is allowed.
        max_retries:               Maximum retries per pipeline run.
        degraded_response_enabled: Whether to attempt degraded response
                                   generation using available signals.
        skip_failed_stages:        Whether to continue the pipeline without
                                   the failed stages (reduced pipeline).
    """
    max_failed_stages: int = 3
    retry_enabled: bool = True
    max_retries: int = 1
    degraded_response_enabled: bool = True
    skip_failed_stages: bool = True


@dataclass
class PipelineResultRecord:
    """Record of a pipeline's final outcome for analytics.

    Attributes:
        company_id:     Tenant identifier.
        ticket_id:      Ticket that was processed.
        variant:        PARWA variant used.
        final_status:   Enum value of the pipeline outcome.
        degradation_level:  Degradation level at completion.
        failed_stages:  List of stage IDs that failed.
        skipped_stages: List of stage IDs that were skipped.
        response_source:  Where the response came from (ai, fallback,
                          handoff).
        timestamp:      UTC ISO-8601 (BC-012).
    """
    company_id: str
    ticket_id: str
    variant: str
    final_status: str
    degradation_level: str
    failed_stages: List[str] = field(default_factory=list)
    skipped_stages: List[str] = field(default_factory=list)
    response_source: str = "ai"
    timestamp: str = ""


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════


# Per-variant degradation configurations
_VARIANT_DEGRADATION_CONFIGS: Dict[str, DegradationConfig] = {
    "mini_parwa": DegradationConfig(
        max_failed_stages=2,
        retry_enabled=False,
        max_retries=0,
        degraded_response_enabled=True,
        skip_failed_stages=True,
    ),
    "parwa": DegradationConfig(
        max_failed_stages=3,
        retry_enabled=True,
        max_retries=1,
        degraded_response_enabled=True,
        skip_failed_stages=True,
    ),
    "high_parwa": DegradationConfig(
        max_failed_stages=4,
        retry_enabled=True,
        max_retries=2,
        degraded_response_enabled=True,
        skip_failed_stages=True,
    ),
}

# Per-variant critical thresholds — when degradation is "critical"
# (more than half of max_failed_stages have failed)
_VARIANT_CRITICAL_THRESHOLD: Dict[str, float] = {
    "mini_parwa": 0.5,   # 1+ failures out of 2
    "parwa": 0.5,         # 2+ failures out of 3
    "high_parwa": 0.5,    # 2+ failures out of 4
}

# Default fallback templates — one per supported intent
_DEFAULT_FALLBACK_TEMPLATES: List[FallbackTemplate] = [
    FallbackTemplate(
        intent="refund_request",
        template=(
            "We understand you have a refund concern. Our team is "
            "reviewing your request and will get back to you "
            "shortly with an update."
        ),
        priority=1,
        requires_signals=[],
    ),
    FallbackTemplate(
        intent="technical_issue",
        template=(
            "We've detected a technical issue with your request. "
            "Our technical team has been notified and will assist "
            "you shortly."
        ),
        priority=1,
        requires_signals=[],
    ),
    FallbackTemplate(
        intent="billing",
        template=(
            "We're looking into your billing inquiry. A specialist "
            "will review your account and follow up with you."
        ),
        priority=1,
        requires_signals=[],
    ),
    FallbackTemplate(
        intent="general",
        template=(
            "Thank you for reaching out. We're processing your "
            "request and will respond as soon as possible."
        ),
        priority=10,
        requires_signals=[],
    ),
    FallbackTemplate(
        intent="complaint",
        template=(
            "We take your feedback seriously. A senior agent has "
            "been assigned to review your concern and will contact "
            "you promptly."
        ),
        priority=1,
        requires_signals=[],
    ),
    FallbackTemplate(
        intent="feature_request",
        template=(
            "Thank you for your suggestion! We've logged your "
            "feature request and our product team will review it."
        ),
        priority=1,
        requires_signals=[],
    ),
]

# Enhanced fallback templates for high_parwa (signal-aware)
_PARWA_HIGH_ENHANCED_TEMPLATES: List[FallbackTemplate] = [
    FallbackTemplate(
        intent="refund_request",
        template=(
            "We understand you have a refund concern regarding "
            "your recent transaction. Our team is reviewing the "
            "details and will reach out with an update within "
            "24 hours."
        ),
        priority=0,  # Higher priority than default
        requires_signals=["order_id", "amount"],
    ),
    FallbackTemplate(
        intent="billing",
        template=(
            "We're reviewing the billing details on your account. "
            "A billing specialist will examine the charge in "
            "question and follow up with a resolution shortly."
        ),
        priority=0,
        requires_signals=["account_id"],
    ),
    FallbackTemplate(
        intent="technical_issue",
        template=(
            "Our technical team has been notified about the issue "
            "you're experiencing. We're investigating and will "
            "provide an update as soon as possible."
        ),
        priority=0,
        requires_signals=["error_code"],
    ),
]

# Stage dependency hints — downstream stages can check these
# to know what upstream data is missing
_DEFAULT_ERROR_CONTEXT_KEYS: List[str] = [
    "missing_signals",
    "failed_stage_ids",
    "partial_results_available",
    "confidence_penalty",
    "retry_eligible",
]

# Maximum number of pipeline result records to retain in memory
_MAX_RESULT_HISTORY: int = 1000

# Maximum failure stat entries per company
_MAX_FAILURE_STATS: int = 500


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> str:
    """Return current UTC timestamp as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _get_variant_config(variant: str) -> DegradationConfig:
    """Retrieve degradation config for a variant with safe fallback."""
    return _VARIANT_DEGRADATION_CONFIGS.get(
        variant, _VARIANT_DEGRADATION_CONFIGS["parwa"],
    )


def _get_critical_ratio(variant: str) -> float:
    """Get the critical degradation ratio for a variant."""
    return _VARIANT_CRITICAL_THRESHOLD.get(variant, 0.5)


def _count_failures(failures: List[StageFailure]) -> int:
    """Count the number of real failures (excluding SKIPPED).

    Only FAILED, TIMEOUT, and DEGRADED count against the
    failure threshold. SKIPPED stages are expected in a
    reduced pipeline and should not penalize the run.
    """
    return sum(
        1 for f in failures
        if f.status
        in (PipelineStageStatus.FAILED, PipelineStageStatus.TIMEOUT)
    )


def _count_all_non_success(failures: List[StageFailure]) -> int:
    """Count all non-success statuses including DEGRADED and SKIPPED."""
    return sum(
        1 for f in failures
        if f.status != PipelineStageStatus.SUCCESS
    )


# ══════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ══════════════════════════════════════════════════════════════════


class PartialFailureHandler:
    """SG-32: Partial Pipeline Failure Handler.

    Manages graceful degradation when individual pipeline stages fail
    but others succeed. Each variant has independent degradation
    settings and fallback template pools.

    Key capabilities:
    - Record stage failures with full context
    - Assess degradation level (none / degraded / critical / handoff)
    - Generate best-effort degraded responses from available signals
    - Build reduced pipelines that skip failed stages
    - Propagate error context to downstream stages
    - Trigger human handoff when failure count exceeds variant threshold
    - Track failure statistics per company for monitoring

    BC-001: company_id first parameter on all public methods.
    BC-008: Every public method wrapped in try/except — never crash.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        """Initialize the handler with default templates and configs.

        Loads per-variant degradation configurations, registers
        default fallback templates, and prepares internal state.
        """
        self._lock = threading.RLock()

        # Fallback template registry: intent -> sorted list of templates
        self._fallback_templates: Dict[str, List[FallbackTemplate]] = (
            defaultdict(list)
        )

        # Per-company custom degradation configs:
        # company_id -> variant -> DegradationConfig
        self._custom_configs: Dict[str, Dict[str, DegradationConfig]] = (
            defaultdict(dict)
        )

        # Pipeline result history for analytics
        # company_id -> list of PipelineResultRecord
        self._result_history: Dict[str, List[PipelineResultRecord]] = (
            defaultdict(list)
        )

        # Failure statistics per company
        # company_id -> list of dicts with stage-level failure info
        self._failure_stats: Dict[str, List[Dict[str, Any]]] = (
            defaultdict(list)
        )

        # Register all default templates
        self._register_default_templates()

        logger.info(
            "partial_failure_handler_initialized",
            default_templates=len(_DEFAULT_FALLBACK_TEMPLATES),
            enhanced_templates=len(_PARWA_HIGH_ENHANCED_TEMPLATES),
            variants_configured=list(_VARIANT_DEGRADATION_CONFIGS.keys()),
        )

    # ── Template Registration ───────────────────────────────────

    def _register_default_templates(self) -> None:
        """Register all built-in fallback templates.

        Includes base templates for all intents plus enhanced
        signal-aware templates for high_parwa variant.
        """
        for tmpl in _DEFAULT_FALLBACK_TEMPLATES:
            self._fallback_templates[tmpl.intent].append(tmpl)

        # Register high_parwa enhanced templates
        for tmpl in _PARWA_HIGH_ENHANCED_TEMPLATES:
            self._fallback_templates[tmpl.intent].append(tmpl)

        # Sort each intent's templates by priority (lower = better)
        for intent in self._fallback_templates:
            self._fallback_templates[intent].sort(
                key=lambda t: t.priority,
            )

    # ── Stage Failure Recording ─────────────────────────────────

    def register_stage_failure(
        self,
        company_id: str,
        ticket_id: str,
        stage_id: str,
        error: str,
        status: PipelineStageStatus,
        pipeline_context: PipelineContext,
        retry_count: int = 0,
    ) -> PipelineContext:
        """Record a stage failure in the pipeline context.

        Appends a StageFailure record to the context's failure list,
        updates the error context dict for downstream stages, and
        updates the available signals tracking.

        Args:
            company_id:       Tenant company identifier (BC-001).
            ticket_id:        Support ticket being processed.
            stage_id:         Identifier of the failed stage.
            error:            Human-readable error description.
            status:           PipelineStageStatus of the failure.
            pipeline_context: Mutable pipeline context to update.
            retry_count:      Number of retries already attempted.

        Returns:
            The updated PipelineContext with failure recorded.
        """
        try:
            failure = StageFailure(
                stage_id=stage_id,
                error=error,
                status=status,
                timestamp=_now_utc(),
                retry_count=retry_count,
            )

            with self._lock:
                pipeline_context.failures.append(failure)

                # Update error context for downstream stages
                self._update_error_context(
                    pipeline_context, failure,
                )

                # Track failure stats
                self._record_failure_stat(
                    company_id, ticket_id, failure, pipeline_context,
                )

            logger.warning(
                "pipeline_stage_failed",
                company_id=company_id,
                ticket_id=ticket_id,
                stage_id=stage_id,
                status=status.value,
                error=error[:200],
                retry_count=retry_count,
                total_failures=len(pipeline_context.failures),
            )

            return pipeline_context

        except Exception:
            logger.exception(
                "register_stage_failure_crashed",
                company_id=company_id,
                ticket_id=ticket_id,
                stage_id=stage_id,
            )
            # BC-008: Return context even on error
            return pipeline_context

    def _update_error_context(
        self,
        ctx: PipelineContext,
        failure: StageFailure,
    ) -> None:
        """Update the error context dict with information from the
        latest failure. This dict is read by downstream stages.

        Updates include:
        - failed_stage_ids: accumulated list of failed stage IDs
        - missing_signals: signals that the failed stage was
          expected to produce
        - confidence_penalty: incremental penalty for degraded
          response quality
        - retry_eligible: whether the stage can be retried
        """
        failed_ids = ctx.error_context.get("failed_stage_ids", [])
        if failure.stage_id not in failed_ids:
            failed_ids.append(failure.stage_id)
        ctx.error_context["failed_stage_ids"] = failed_ids

        # Estimate missing signals from the failed stage
        # (heuristic based on common stage-to-signal mappings)
        stage_signal_map: Dict[str, List[str]] = {
            "signal_extraction": [
                "intent", "sentiment", "urgency", "language",
            ],
            "rag_retrieval": ["knowledge_context", "relevant_docs"],
            "sentiment_analysis": ["sentiment", "emotion"],
            "classification": ["intent", "category", "priority"],
            "response_generation": ["response_text"],
            "guardrails": ["safety_score", "pii_flags"],
            "context_compression": ["compressed_context"],
            "conversation_summarization": ["summary"],
        }
        missing = stage_signal_map.get(failure.stage_id, [])
        existing_missing = ctx.error_context.get("missing_signals", [])
        for sig in missing:
            if sig not in existing_missing:
                existing_missing.append(sig)
        ctx.error_context["missing_signals"] = existing_missing

        # Track which partial results are still available
        ctx.error_context["partial_results_available"] = (
            len(ctx.stage_results) > 0
        )

        # Increment confidence penalty for each failure
        current_penalty = ctx.error_context.get("confidence_penalty", 0.0)
        if failure.status == PipelineStageStatus.FAILED:
            current_penalty += 0.15
        elif failure.status == PipelineStageStatus.TIMEOUT:
            current_penalty += 0.10
        elif failure.status == PipelineStageStatus.DEGRADED:
            current_penalty += 0.05
        ctx.error_context["confidence_penalty"] = min(
            current_penalty, 0.75,  # Cap at 75% penalty
        )

        # Check retry eligibility
        variant_config = _get_variant_config(ctx.variant)
        ctx.error_context["retry_eligible"] = (
            variant_config.retry_enabled
            and failure.retry_count < variant_config.max_retries
            and failure.status != PipelineStageStatus.TIMEOUT
        )

        # Record the latest failure timestamp
        ctx.error_context["last_failure_timestamp"] = failure.timestamp

    def _record_failure_stat(
        self,
        company_id: str,
        ticket_id: str,
        failure: StageFailure,
        ctx: PipelineContext,
    ) -> None:
        """Append a failure stat entry for company-level analytics."""
        stat: Dict[str, Any] = {
            "ticket_id": ticket_id,
            "stage_id": failure.stage_id,
            "status": failure.status.value,
            "error": failure.error[:200],
            "timestamp": failure.timestamp,
            "variant": ctx.variant,
            "intent": ctx.intent,
            "retry_count": failure.retry_count,
        }
        stats = self._failure_stats[company_id]
        stats.append(stat)
        if len(stats) > _MAX_FAILURE_STATS:
            self._failure_stats[company_id] = stats[-_MAX_FAILURE_STATS:]

    # ── Degradation Level Assessment ────────────────────────────

    def get_degradation_level(
        self,
        pipeline_context: PipelineContext,
    ) -> str:
        """Assess the overall degradation level for a pipeline run.

        Compares the number of failed stages against the variant's
        configured thresholds to determine one of four levels:
        "none", "degraded", "critical", or "human_handoff".

        Args:
            pipeline_context: Current pipeline context with failures.

        Returns:
            Degradation level string (DegradationLevel enum value).
        """
        try:
            with self._lock:
                failures = pipeline_context.failures
                if not failures:
                    return DegradationLevel.NONE.value

                variant = pipeline_context.variant or "parwa"
                config = self._get_effective_config(
                    pipeline_context.company_id, variant,
                )

                failed_count = _count_failures(failures)
                total_failures = _count_all_non_success(failures)

                # Check human handoff threshold
                if failed_count >= config.max_failed_stages:
                    return DegradationLevel.HUMAN_HANDOFF.value

                # Check critical threshold
                critical_ratio = _get_critical_ratio(variant)
                if (failed_count / config.max_failed_stages
                        >= critical_ratio):
                    return DegradationLevel.CRITICAL.value

                # At least one failure means degraded
                if failed_count > 0:
                    return DegradationLevel.DEGRADED.value

                # Only SKIPPED or DEGRADED — treat as degraded
                if total_failures > 0:
                    return DegradationLevel.DEGRADED.value

                return DegradationLevel.NONE.value

        except Exception:
            logger.exception(
                "get_degradation_level_crashed",
                company_id=pipeline_context.company_id,
                ticket_id=pipeline_context.ticket_id,
            )
            # BC-008: Return safe default
            return DegradationLevel.DEGRADED.value

    # ── Degraded Response Generation ────────────────────────────

    def generate_degraded_response(
        self,
        pipeline_context: PipelineContext,
    ) -> str:
        """Generate a best-effort response using available signals
        and fallback templates.

        When pipeline stages have failed, this method assembles a
        response by:
        1. Finding the best matching fallback template for the intent
        2. Enriching it with any available signal data
        3. Falling back to a generic response if no template matches

        Args:
            pipeline_context: Pipeline context with partial results
                              and recorded failures.

        Returns:
            A degraded response string ready for delivery.
        """
        try:
            intent = pipeline_context.intent or "general"
            variant = pipeline_context.variant or "parwa"
            available = list(pipeline_context.available_signals)
            signals = dict(pipeline_context.signals)

            # Attempt to find a matching fallback template
            template = self.get_fallback_template(
                intent, variant, available,
            )

            if template:
                # Enrich template with available signal data
                enriched = self._enrich_template(
                    template, signals, pipeline_context,
                )
                logger.info(
                    "degraded_response_generated_from_template",
                    company_id=pipeline_context.company_id,
                    ticket_id=pipeline_context.ticket_id,
                    intent=intent,
                    variant=variant,
                    available_signals=len(available),
                )
                return enriched

            # No template found — generate from available signals
            response = self._generate_from_signals(
                signals, pipeline_context,
            )
            if response:
                logger.info(
                    "degraded_response_generated_from_signals",
                    company_id=pipeline_context.company_id,
                    ticket_id=pipeline_context.ticket_id,
                    intent=intent,
                    signal_count=len(signals),
                )
                return response

            # Last resort: generic degraded response
            logger.warning(
                "degraded_response_fallback_generic",
                company_id=pipeline_context.company_id,
                ticket_id=pipeline_context.ticket_id,
                intent=intent,
            )
            return (
                "Thank you for your patience. We're currently "
                "experiencing some processing difficulties. "
                "A team member has been notified and will "
                "assist you shortly."
            )

        except Exception:
            logger.exception(
                "generate_degraded_response_crashed",
                company_id=pipeline_context.company_id,
                ticket_id=pipeline_context.ticket_id,
            )
            # BC-008: Always return something usable
            return (
                "Thank you for contacting us. We're processing "
                "your request and will follow up with you shortly."
            )

    def _enrich_template(
        self,
        template: str,
        signals: Dict[str, Any],
        ctx: PipelineContext,
    ) -> str:
        """Enrich a fallback template with available signal data.

        Performs simple placeholder substitution if the template
        contains {{signal_name}} patterns. If no placeholders
        are found, the template is returned as-is.

        Args:
            template: Fallback template string.
            signals:  Available signal key-value pairs.
            ctx:      Pipeline context for additional info.

        Returns:
            Enriched response string.
        """
        response = template

        # Replace {{signal_name}} placeholders with signal values
        placeholder_map: Dict[str, str] = {
            "{{order_id}}": str(signals.get("order_id", "")),
            "{{amount}}": str(signals.get("amount", "")),
            "{{account_id}}": str(signals.get("account_id", "")),
            "{{error_code}}": str(signals.get("error_code", "")),
            "{{product_name}}": str(signals.get("product_name", "")),
            "{{ticket_id}}": ctx.ticket_id,
            "{{company_name}}": str(
                signals.get("company_name", "our team"),
            ),
            "{{customer_name}}": str(
                signals.get("customer_name", ""),
            ),
            "{{urgency}}": str(signals.get("urgency", "")),
            "{{sentiment}}": str(signals.get("sentiment", "")),
        }

        for placeholder, value in placeholder_map.items():
            if placeholder in response and value:
                response = response.replace(placeholder, value)

        # Append context about degradation if failures exist
        if ctx.failures:
            failed_names = [f.stage_id for f in ctx.failures]
            # Don't expose internal details to the customer;
            # this is for internal logging only
            ctx.metadata["degradation_info"] = {
                "failed_stages": failed_names,
                "available_signals": ctx.available_signals,
                "degradation_level": self.get_degradation_level(ctx),
            }

        return response

    def _generate_from_signals(
        self,
        signals: Dict[str, Any],
        ctx: PipelineContext,
    ) -> Optional[str]:
        """Attempt to generate a response from available signal data
        without a template.

        Constructs a simple acknowledgment using the intent and any
        extracted signals to provide a slightly more contextual
        response than the generic fallback.

        Args:
            signals: Available signal key-value pairs.
            ctx:      Pipeline context.

        Returns:
            Generated response string, or None if insufficient data.
        """
        if not signals:
            return None

        intent = ctx.intent or "general"
        parts: List[str] = []

        # Build intent-specific preamble
        intent_preambles: Dict[str, str] = {
            "refund_request": "Regarding your refund request",
            "technical_issue": "About the technical issue",
            "billing": "Regarding your billing inquiry",
            "complaint": "Concerning your feedback",
            "feature_request": "About your suggestion",
        }
        preamble = intent_preambles.get(intent, "Regarding your inquiry")
        parts.append(f"{preamble} — ")

        # Add signal-derived context
        if signals.get("order_id"):
            parts.append(
                f"related to order {signals['order_id']}. "
            )
        if signals.get("product_name"):
            parts.append(
                f"concerning {signals['product_name']}. "
            )
        if signals.get("urgency") == "high":
            parts.append(
                "We understand this is urgent. "
            )

        parts.append(
            "Our team is reviewing the details and will "
            "respond as soon as possible."
        )

        response = "".join(parts)
        return response if len(response) > 30 else None

    # ── Reduced Pipeline Builder ────────────────────────────────

    def build_reduced_pipeline(
        self,
        pipeline_context: PipelineContext,
        full_step_ids: List[str],
    ) -> List[str]:
        """Build a reduced pipeline by removing failed stages.

        Takes the original full pipeline step list and removes any
        stages that have recorded failures. The remaining stages
        preserve their original execution order.

        Stages marked as SKIPPED are also excluded since they were
        already bypassed in a previous reduced pipeline attempt.

        Args:
            pipeline_context: Context with recorded failures.
            full_step_ids:    Ordered list of all pipeline step IDs.

        Returns:
            Ordered list of remaining pipeline step IDs.
        """
        try:
            with self._lock:
                if not pipeline_context.failures:
                    return list(full_step_ids)

                # Collect IDs of stages that should be excluded
                excluded: set[str] = set()
                for failure in pipeline_context.failures:
                    if failure.status in (
                        PipelineStageStatus.FAILED,
                        PipelineStageStatus.TIMEOUT,
                        PipelineStageStatus.SKIPPED,
                    ):
                        excluded.add(failure.stage_id)

                # Filter while preserving order
                reduced = [
                    step_id
                    for step_id in full_step_ids
                    if step_id not in excluded
                ]

                # Record skipped stages in metadata
                skipped = [
                    step_id
                    for step_id in full_step_ids
                    if step_id in excluded
                ]
                pipeline_context.metadata["skipped_stages"] = skipped
                pipeline_context.metadata["reduced_pipeline"] = reduced

                logger.info(
                    "reduced_pipeline_built",
                    company_id=pipeline_context.company_id,
                    ticket_id=pipeline_context.ticket_id,
                    original_steps=len(full_step_ids),
                    reduced_steps=len(reduced),
                    skipped_steps=len(skipped),
                    skipped_ids=skipped,
                )

                return reduced

        except Exception:
            logger.exception(
                "build_reduced_pipeline_crashed",
                company_id=pipeline_context.company_id,
                ticket_id=pipeline_context.ticket_id,
            )
            # BC-008: Return original pipeline as safe fallback
            return list(full_step_ids)

    # ── Human Handoff Decision ──────────────────────────────────

    def should_trigger_human_handoff(
        self,
        pipeline_context: PipelineContext,
    ) -> bool:
        """Determine whether failures exceed the variant threshold
        and human handoff should be triggered.

        Compares the count of real failures (FAILED, TIMEOUT) against
        the variant's max_failed_stages configuration. If the count
        meets or exceeds the threshold, returns True.

        Args:
            pipeline_context: Pipeline context with recorded failures.

        Returns:
            True if human handoff should be triggered, False otherwise.
        """
        try:
            with self._lock:
                variant = pipeline_context.variant or "parwa"
                config = self._get_effective_config(
                    pipeline_context.company_id, variant,
                )
                failed_count = _count_failures(pipeline_context.failures)
                should_handoff = (
                    failed_count >= config.max_failed_stages
                )

                if should_handoff:
                    logger.warning(
                        "human_handoff_triggered",
                        company_id=pipeline_context.company_id,
                        ticket_id=pipeline_context.ticket_id,
                        variant=variant,
                        failed_count=failed_count,
                        threshold=config.max_failed_stages,
                        failed_stages=[
                            f.stage_id
                            for f in pipeline_context.failures
                        ],
                    )

                return should_handoff

        except Exception:
            logger.exception(
                "should_trigger_human_handoff_crashed",
                company_id=pipeline_context.company_id,
                ticket_id=pipeline_context.ticket_id,
            )
            # BC-008: Err on the side of caution — escalate
            return True

    # ── Error Context Propagation ───────────────────────────────

    def propagate_error_context(
        self,
        pipeline_context: PipelineContext,
    ) -> Dict[str, Any]:
        """Build a comprehensive error context dict from all recorded
        failures for propagation to downstream stages.

        The error context enables downstream stages to adapt their
        behaviour based on what went wrong upstream. For example,
        a response generation stage can use a fallback template if
        signal extraction failed.

        Args:
            pipeline_context: Pipeline context with failures and
                              existing error context.

        Returns:
            Dict containing all error context for downstream stages.
        """
        try:
            with self._lock:
                failures = pipeline_context.failures
                base_context = dict(pipeline_context.error_context)

                if not failures:
                    base_context["has_failures"] = False
                    return base_context

                # Build comprehensive error context
                error_context: Dict[str, Any] = {
                    "has_failures": True,
                    "total_failure_count": len(failures),
                    "real_failure_count": _count_failures(failures),
                    "degradation_level": self.get_degradation_level(
                        pipeline_context,
                    ),
                    "failed_stage_ids": base_context.get(
                        "failed_stage_ids", [],
                    ),
                    "missing_signals": base_context.get(
                        "missing_signals", [],
                    ),
                    "confidence_penalty": base_context.get(
                        "confidence_penalty", 0.0,
                    ),
                    "retry_eligible": base_context.get(
                        "retry_eligible", False,
                    ),
                    "partial_results_available": (
                        len(pipeline_context.stage_results) > 0
                    ),
                    "available_signals_count": len(
                        pipeline_context.available_signals,
                    ),
                }

                # Add per-stage failure details
                stage_errors: List[Dict[str, Any]] = []
                for failure in failures:
                    stage_errors.append({
                        "stage_id": failure.stage_id,
                        "status": failure.status.value,
                        "error": failure.error,
                        "timestamp": failure.timestamp,
                        "retry_count": failure.retry_count,
                    })
                error_context["stage_errors"] = stage_errors

                # Add handoff recommendation
                variant = pipeline_context.variant or "parwa"
                config = self._get_effective_config(
                    pipeline_context.company_id, variant,
                )
                error_context["handoff_recommended"] = (
                    _count_failures(failures) >= config.max_failed_stages
                )

                # Add retry recommendation
                error_context["retry_recommended"] = (
                    config.retry_enabled
                    and _count_failures(failures) < config.max_failed_stages
                    and any(
                        f.retry_count < config.max_retries
                        for f in failures
                        if f.status == PipelineStageStatus.FAILED
                    )
                )

                # Merge with any existing keys from base context
                for key, value in base_context.items():
                    if key not in error_context:
                        error_context[key] = value

                logger.debug(
                    "error_context_propagated",
                    company_id=pipeline_context.company_id,
                    ticket_id=pipeline_context.ticket_id,
                    failure_count=len(failures),
                    degradation_level=error_context["degradation_level"],
                )

                return error_context

        except Exception:
            logger.exception(
                "propagate_error_context_crashed",
                company_id=pipeline_context.company_id,
                ticket_id=pipeline_context.ticket_id,
            )
            # BC-008: Return minimal safe context
            return {
                "has_failures": True,
                "total_failure_count": len(pipeline_context.failures),
                "degradation_level": DegradationLevel.DEGRADED.value,
                "confidence_penalty": 0.25,
            }

    # ── Fallback Template Lookup ────────────────────────────────

    def get_fallback_template(
        self,
        intent: str,
        variant: str,
        available_signals: List[str],
    ) -> Optional[str]:
        """Find the best matching fallback template for an intent.

        Selection process:
        1. Look up templates registered for the given intent
        2. Filter by variant compatibility (high_parwa gets enhanced)
        3. Prefer templates whose required_signals are all available
        4. Among matches, select the one with lowest priority number
        5. If no intent-specific match, fall back to "general"

        Args:
            intent:            Customer intent string.
            variant:           PARWA variant (affects template pool).
            available_signals: Names of signals that were extracted.

        Returns:
            Best matching template string, or None if no match.
        """
        try:
            with self._lock:
                templates = self._fallback_templates.get(intent, [])
                if not templates:
                    # Fall back to "general" intent
                    templates = self._fallback_templates.get(
                        "general", [],
                    )
                if not templates:
                    return None

                # Score each template
                best_template: Optional[FallbackTemplate] = None
                best_score: float = -1.0

                for tmpl in templates:
                    score = self._score_template(
                        tmpl, variant, available_signals,
                    )
                    if score > best_score:
                        best_score = score
                        best_template = tmpl

                if best_template and best_score > 0:
                    return best_template.template

                return None

        except Exception:
            logger.exception(
                "get_fallback_template_crashed",
                intent=intent,
                variant=variant,
            )
            return None

    def _score_template(
        self,
        template: FallbackTemplate,
        variant: str,
        available_signals: List[str],
    ) -> float:
        """Score a fallback template for relevance to the current
        pipeline state.

        Scoring criteria:
        - Base score: 100 - priority (lower priority = higher base)
        - Signal match bonus: +50 if all required signals available
        - Partial signal bonus: +25 if some required signals available
        - Variant match bonus: +20 for high_parwa enhanced templates
          when variant is high_parwa

        Args:
            template:         Template to score.
            variant:          Current PARWA variant.
            available_signals: Names of available signals.

        Returns:
            Numeric score (higher = better match).
        """
        score = 100.0 - (template.priority * 5.0)

        # Check required signals
        if template.requires_signals:
            available_set = set(available_signals)
            required_set = set(template.requires_signals)
            if required_set.issubset(available_set):
                score += 50.0
            elif required_set.intersection(available_set):
                score += 25.0
        else:
            # No signal requirements — small bonus
            score += 10.0

        # Variant-specific bonus for enhanced templates
        if variant == "high_parwa" and template.priority == 0:
            score += 20.0

        # Slight penalty for higher-priority (less relevant) templates
        score -= template.priority * 2.0

        return max(0.0, score)

    # ── Pipeline Result Recording ───────────────────────────────

    def record_pipeline_result(
        self,
        company_id: str,
        ticket_id: str,
        pipeline_context: PipelineContext,
        final_status: str,
    ) -> PipelineResultRecord:
        """Record the final outcome of a pipeline run.

        Creates a PipelineResultRecord with all relevant details and
        appends it to the company's result history. The record
        includes degradation level, failed/skipped stages, and the
        source of the response that was delivered.

        Args:
            company_id:       Tenant company identifier (BC-001).
            ticket_id:        Support ticket that was processed.
            pipeline_context: Final pipeline context at end of run.
            final_status:     PipelineFinalStatus enum value string.

        Returns:
            The recorded PipelineResultRecord.
        """
        try:
            degradation = self.get_degradation_level(pipeline_context)

            failed_stages = [
                f.stage_id
                for f in pipeline_context.failures
                if f.status != PipelineStageStatus.SKIPPED
            ]
            skipped_stages = [
                f.stage_id
                for f in pipeline_context.failures
                if f.status == PipelineStageStatus.SKIPPED
            ]

            # Determine response source based on degradation
            if degradation == DegradationLevel.HUMAN_HANDOFF.value:
                response_source = "handoff"
            elif degradation == DegradationLevel.NONE.value:
                response_source = "ai"
            else:
                # Check if a template was used
                template_used = pipeline_context.metadata.get(
                    "template_used",
                )
                response_source = (
                    "fallback" if template_used else "degraded_ai"
                )

            record = PipelineResultRecord(
                company_id=company_id,
                ticket_id=ticket_id,
                variant=pipeline_context.variant or "parwa",
                final_status=final_status,
                degradation_level=degradation,
                failed_stages=failed_stages,
                skipped_stages=skipped_stages,
                response_source=response_source,
                timestamp=_now_utc(),
            )

            with self._lock:
                history = self._result_history[company_id]
                history.append(record)
                if len(history) > _MAX_RESULT_HISTORY:
                    self._result_history[company_id] = (
                        history[-_MAX_RESULT_HISTORY:]
                    )

            logger.info(
                "pipeline_result_recorded",
                company_id=company_id,
                ticket_id=ticket_id,
                variant=record.variant,
                final_status=final_status,
                degradation_level=degradation,
                failed_stages=failed_stages,
                response_source=response_source,
            )

            return record

        except Exception:
            logger.exception(
                "record_pipeline_result_crashed",
                company_id=company_id,
                ticket_id=ticket_id,
            )
            # BC-008: Return a minimal record
            return PipelineResultRecord(
                company_id=company_id,
                ticket_id=ticket_id,
                variant=pipeline_context.variant or "parwa",
                final_status=PipelineFinalStatus.FULL_FAILURE.value,
                degradation_level=DegradationLevel.DEGRADED.value,
                timestamp=_now_utc(),
            )

    # ── Failure Statistics ──────────────────────────────────────

    def get_failure_stats(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get aggregated failure statistics for a company.

        Returns per-stage failure counts, top error messages,
        failure rate by variant, and recent failure trends.

        Args:
            company_id: Tenant company identifier (BC-001).

        Returns:
            Dict containing aggregated failure statistics.
        """
        try:
            with self._lock:
                stats = list(self._failure_stats.get(company_id, []))

            if not stats:
                return {
                    "company_id": company_id,
                    "total_failures": 0,
                    "stage_breakdown": {},
                    "variant_breakdown": {},
                    "top_errors": [],
                    "recent_failures": [],
                }

            # Per-stage breakdown
            stage_counts: Dict[str, int] = defaultdict(int)
            stage_errors: Dict[str, List[str]] = defaultdict(list)

            # Per-variant breakdown
            variant_counts: Dict[str, int] = defaultdict(int)

            # Status breakdown
            status_counts: Dict[str, int] = defaultdict(int)

            for stat in stats:
                stage_id = stat.get("stage_id", "unknown")
                stage_counts[stage_id] += 1
                error_msg = stat.get("error", "")
                if error_msg and len(error_msg) > 10:
                    if len(stage_errors[stage_id]) < 5:
                        stage_errors[stage_id].append(error_msg)
                variant = stat.get("variant", "unknown")
                variant_counts[variant] += 1
                status = stat.get("status", "unknown")
                status_counts[status] += 1

            # Top errors across all stages
            all_errors: Dict[str, int] = defaultdict(int)
            for stat in stats:
                error_msg = stat.get("error", "unknown")
                all_errors[error_msg] += 1
            top_errors = sorted(
                all_errors.items(), key=lambda x: x[1], reverse=True,
            )[:10]

            # Recent failures (last 20)
            recent = stats[-20:]

            # Pipeline result summary
            result_history = list(
                self._result_history.get(company_id, []),
            )
            result_summary: Dict[str, int] = defaultdict(int)
            for r in result_history:
                result_summary[r.final_status] += 1

            # Handoff rate
            handoff_count = result_summary.get(
                PipelineFinalStatus.HUMAN_HANDOFF_TRIGGERED.value, 0,
            )
            total_results = len(result_history) or 1
            handoff_rate = round(handoff_count / total_results, 4)

            return {
                "company_id": company_id,
                "total_failures": len(stats),
                "stage_breakdown": dict(stage_counts),
                "stage_top_errors": {
                    k: v for k, v in stage_errors.items()
                },
                "variant_breakdown": dict(variant_counts),
                "status_breakdown": dict(status_counts),
                "top_errors": [
                    {"error": err, "count": cnt}
                    for err, cnt in top_errors
                ],
                "recent_failures": recent,
                "result_summary": dict(result_summary),
                "handoff_rate": handoff_rate,
                "total_pipeline_runs": len(result_history),
                "generated_at": _now_utc(),
            }

        except Exception:
            logger.exception(
                "get_failure_stats_crashed",
                company_id=company_id,
            )
            # BC-008: Return minimal safe stats
            return {
                "company_id": company_id,
                "total_failures": 0,
                "stage_breakdown": {},
                "variant_breakdown": {},
                "top_errors": [],
                "recent_failures": [],
                "generated_at": _now_utc(),
            }

    # ── Variant Configuration ───────────────────────────────────

    def configure_variant(
        self,
        company_id: str,
        variant: str,
        config_overrides: Dict[str, Any],
    ) -> bool:
        """Customize degradation settings for a company's variant.

        Merges the provided overrides with the base variant config.
        Only known configuration keys are accepted; unknown keys are
        silently ignored.

        Accepted override keys:
        - max_failed_stages (int)
        - retry_enabled (bool)
        - max_retries (int)
        - degraded_response_enabled (bool)
        - skip_failed_stages (bool)

        Args:
            company_id:       Tenant company identifier (BC-001).
            variant:          PARWA variant to configure.
            config_overrides: Dict of config key-value pairs to override.

        Returns:
            True if configuration was applied, False on error.
        """
        try:
            with self._lock:
                base = _get_variant_config(variant)

                # Build updated config from base + overrides
                updated = DegradationConfig(
                    max_failed_stages=config_overrides.get(
                        "max_failed_stages",
                        base.max_failed_stages,
                    ),
                    retry_enabled=config_overrides.get(
                        "retry_enabled",
                        base.retry_enabled,
                    ),
                    max_retries=config_overrides.get(
                        "max_retries",
                        base.max_retries,
                    ),
                    degraded_response_enabled=config_overrides.get(
                        "degraded_response_enabled",
                        base.degraded_response_enabled,
                    ),
                    skip_failed_stages=config_overrides.get(
                        "skip_failed_stages",
                        base.skip_failed_stages,
                    ),
                )

                if company_id not in self._custom_configs:
                    self._custom_configs[company_id] = {}

                self._custom_configs[company_id][variant] = updated

                logger.info(
                    "variant_config_updated",
                    company_id=company_id,
                    variant=variant,
                    overrides=config_overrides,
                    new_config={
                        "max_failed_stages": updated.max_failed_stages,
                        "retry_enabled": updated.retry_enabled,
                        "max_retries": updated.max_retries,
                        "degraded_response_enabled": (
                            updated.degraded_response_enabled
                        ),
                        "skip_failed_stages": updated.skip_failed_stages,
                    },
                )

                return True

        except Exception:
            logger.exception(
                "configure_variant_crashed",
                company_id=company_id,
                variant=variant,
                overrides=config_overrides,
            )
            return False

    def _get_effective_config(
        self,
        company_id: str,
        variant: str,
    ) -> DegradationConfig:
        """Get the effective degradation config for a company+variant.

        Checks for custom configs first, then falls back to the
        default variant config.

        Args:
            company_id: Tenant company identifier.
            variant:    PARWA variant.

        Returns:
            Effective DegradationConfig.
        """
        custom = self._custom_configs.get(company_id, {})
        if variant in custom:
            return custom[variant]
        return _get_variant_config(variant)

    # ── Utility Methods ─────────────────────────────────────────

    def get_variant_config(
        self,
        company_id: str,
        variant: str,
    ) -> Dict[str, Any]:
        """Get the current degradation configuration for a company
        and variant as a plain dict.

        Useful for API responses and debugging.

        Args:
            company_id: Tenant company identifier (BC-001).
            variant:    PARWA variant.

        Returns:
            Dict representation of the DegradationConfig.
        """
        try:
            config = self._get_effective_config(company_id, variant)
            return {
                "company_id": company_id,
                "variant": variant,
                "max_failed_stages": config.max_failed_stages,
                "retry_enabled": config.retry_enabled,
                "max_retries": config.max_retries,
                "degraded_response_enabled": (
                    config.degraded_response_enabled
                ),
                "skip_failed_stages": config.skip_failed_stages,
                "is_custom": (
                    company_id in self._custom_configs
                    and variant in self._custom_configs[company_id]
                ),
            }
        except Exception:
            logger.exception(
                "get_variant_config_crashed",
                company_id=company_id,
                variant=variant,
            )
            return {
                "company_id": company_id,
                "variant": variant,
                "max_failed_stages": 3,
                "retry_enabled": True,
                "max_retries": 1,
                "degraded_response_enabled": True,
                "skip_failed_stages": True,
                "is_custom": False,
            }

    def register_custom_template(
        self,
        company_id: str,
        intent: str,
        template: str,
        priority: int = 10,
        requires_signals: Optional[List[str]] = None,
    ) -> bool:
        """Register a custom fallback template for a company.

        Custom templates are scoped per company and take precedence
        over default templates for the same intent.

        Args:
            company_id:       Tenant company identifier (BC-001).
            intent:           Customer intent to match.
            template:         Fallback response text.
            priority:         Priority (lower = higher precedence).
            requires_signals: Optional signal requirements.

        Returns:
            True if template was registered, False on error.
        """
        try:
            custom_template = FallbackTemplate(
                intent=f"custom:{company_id}:{intent}",
                template=template,
                priority=priority - 1,  # Slightly higher than same priority
                requires_signals=requires_signals or [],
            )

            with self._lock:
                key = f"custom:{company_id}:{intent}"
                self._fallback_templates[key].append(custom_template)
                self._fallback_templates[key].sort(
                    key=lambda t: t.priority,
                )

            logger.info(
                "custom_template_registered",
                company_id=company_id,
                intent=intent,
                priority=priority,
            )
            return True

        except Exception:
            logger.exception(
                "register_custom_template_crashed",
                company_id=company_id,
                intent=intent,
            )
            return False

    def get_pipeline_summary(
        self,
        company_id: str,
        ticket_id: str,
        pipeline_context: PipelineContext,
    ) -> Dict[str, Any]:
        """Get a comprehensive summary of a pipeline's state.

        Useful for logging, debugging, and monitoring dashboards.
        Includes degradation level, failure details, error context,
        and recommendations.

        Args:
            company_id:       Tenant company identifier (BC-001).
            ticket_id:        Support ticket being processed.
            pipeline_context: Current pipeline context.

        Returns:
            Dict with full pipeline state summary.
        """
        try:
            degradation = self.get_degradation_level(pipeline_context)
            should_handoff = self.should_trigger_human_handoff(
                pipeline_context,
            )
            error_context = self.propagate_error_context(
                pipeline_context,
            )

            # Build recommendations based on state
            recommendations = self._build_recommendations(
                pipeline_context, degradation, should_handoff,
            )

            return {
                "company_id": company_id,
                "ticket_id": ticket_id,
                "variant": pipeline_context.variant,
                "intent": pipeline_context.intent,
                "degradation_level": degradation,
                "should_handoff": should_handoff,
                "total_failures": len(pipeline_context.failures),
                "failed_stage_ids": [
                    f.stage_id for f in pipeline_context.failures
                    if f.status != PipelineStageStatus.SKIPPED
                ],
                "skipped_stage_ids": [
                    f.stage_id for f in pipeline_context.failures
                    if f.status == PipelineStageStatus.SKIPPED
                ],
                "available_signals": pipeline_context.available_signals,
                "available_signals_count": len(
                    pipeline_context.available_signals,
                ),
                "stage_results_count": len(pipeline_context.stage_results),
                "confidence_penalty": error_context.get(
                    "confidence_penalty", 0.0,
                ),
                "retry_eligible": error_context.get(
                    "retry_eligible", False,
                ),
                "recommendations": recommendations,
                "error_context": error_context,
                "timestamp": _now_utc(),
            }

        except Exception:
            logger.exception(
                "get_pipeline_summary_crashed",
                company_id=company_id,
                ticket_id=ticket_id,
            )
            return {
                "company_id": company_id,
                "ticket_id": ticket_id,
                "degradation_level": DegradationLevel.DEGRADED.value,
                "error": "Failed to generate pipeline summary",
                "timestamp": _now_utc(),
            }

    def _build_recommendations(
        self,
        ctx: PipelineContext,
        degradation: str,
        should_handoff: bool,
    ) -> List[str]:
        """Build actionable recommendations based on pipeline state.

        Provides guidance for operators and automated recovery
        systems on what actions to take given the current state.

        Args:
            ctx:           Pipeline context.
            degradation:   Current degradation level.
            should_handoff: Whether handoff is recommended.

        Returns:
            List of recommendation strings.
        """
        recommendations: List[str] = []

        if degradation == DegradationLevel.NONE.value:
            recommendations.append(
                "Pipeline is healthy — no action needed.",
            )
            return recommendations

        if should_handoff:
            recommendations.append(
                "CRITICAL: Human handoff recommended. Too many "
                "pipeline stages have failed.",
            )

        if degradation == DegradationLevel.CRITICAL.value:
            recommendations.append(
                "Pipeline is in critical state. Consider using "
                "reduced pipeline with only essential stages.",
            )

        if degradation == DegradationLevel.DEGRADED.value:
            failed_ids = [
                f.stage_id for f in ctx.failures
                if f.status != PipelineStageStatus.SKIPPED
            ]
            recommendations.append(
                f"Degraded pipeline: {len(failed_ids)} stage(s) "
                f"failed: {', '.join(failed_ids)}. "
                "Using fallback response generation.",
            )

            # Check if retry is viable
            config = self._get_effective_config(
                ctx.company_id, ctx.variant or "parwa",
            )
            if config.retry_enabled:
                retryable = [
                    f for f in ctx.failures
                    if f.status == PipelineStageStatus.FAILED
                    and f.retry_count < config.max_retries
                ]
                if retryable:
                    recommendations.append(
                        f"{len(retryable)} stage(s) are eligible "
                        "for retry: "
                        f"{', '.join(f.stage_id for f in retryable)}.",
                    )

        # Signal-based recommendations
        if ctx.available_signals:
            recommendations.append(
                f"{len(ctx.available_signals)} signal(s) available "
                "for degraded response: "
                f"{', '.join(ctx.available_signals[:5])}.",
            )
        else:
            recommendations.append(
                "No signals available — response will use "
                "generic fallback template.",
            )

        return recommendations

    # ── Reset / Testing ─────────────────────────────────────────

    def reset(self) -> None:
        """Clear all internal state. For testing only."""
        try:
            with self._lock:
                self._custom_configs.clear()
                self._result_history.clear()
                self._failure_stats.clear()
                self._fallback_templates.clear()
                self._register_default_templates()

            logger.info("partial_failure_handler_reset")
        except Exception:
            logger.exception("partial_failure_handler_reset_crashed")

    def reset_company(self, company_id: str) -> None:
        """Clear all state for a specific company.

        Removes custom configs, result history, and failure stats.

        Args:
            company_id: Tenant company identifier (BC-001).
        """
        try:
            with self._lock:
                self._custom_configs.pop(company_id, None)
                self._result_history.pop(company_id, None)
                self._failure_stats.pop(company_id, None)

                # Remove custom templates for this company
                keys_to_remove = [
                    key for key in self._fallback_templates
                    if key.startswith(f"custom:{company_id}:")
                ]
                for key in keys_to_remove:
                    del self._fallback_templates[key]

            logger.info(
                "partial_failure_handler_company_reset",
                company_id=company_id,
            )
        except Exception:
            logger.exception(
                "reset_company_crashed",
                company_id=company_id,
            )
