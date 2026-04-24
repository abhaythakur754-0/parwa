"""
Execution Lifecycle Management for AI Agent Call/Session Processing (Week 10 Day 5)

Tracks the full lifecycle of a call/session through pipeline stages,
manages transitions, retries, timeouts, and provides observability
into the processing workflow for each company tenant.

Core Responsibilities:
- Initialize and track lifecycle instances per ticket/company
- Manage stage-by-stage execution progression through the pipeline
- Handle retries, timeouts, and graceful degradation on failure
- Emit lifecycle events to registered listeners for monitoring
- Maintain per-company history and aggregated statistics
- Support three PARWA variants: mini_parwa, parwa, high_parwa

Pipeline stages (variant-dependent):
  mini_parwa:  signal_extraction → intent_classification →
               response_generation → guardrails_check
  parwa:       signal_extraction → intent_classification → rag_retrieval →
               context_compression → response_generation →
               guardrails_check → post_processing
  high_parwa:  (same as parwa)

Building Codes: BC-001, BC-008, BC-012
"""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("call_lifecycle")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class LifecycleStage(str, Enum):
    """Stages of a call/session lifecycle.

    Each stage represents a discrete processing step in the
    AI agent pipeline. Not all stages are used in every variant
    (e.g. mini_parwa skips rag_retrieval and context_compression).
    """
    INITIALIZED = "initialized"
    SIGNAL_EXTRACTION = "signal_extraction"
    INTENT_CLASSIFICATION = "intent_classification"
    RAG_RETRIEVAL = "rag_retrieval"
    CONTEXT_COMPRESSION = "context_compression"
    RESPONSE_GENERATION = "response_generation"
    GUARDRAILS_CHECK = "guardrails_check"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LifecycleEvent(str, Enum):
    """Types of lifecycle events emitted during processing.

    Events are dispatched to registered listeners for monitoring,
    alerting, and observability integration.
    """
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    STAGE_SKIPPED = "stage_skipped"
    STAGE_RETRY = "stage_retry"
    LIFECYCLE_STARTED = "lifecycle_started"
    LIFECYCLE_COMPLETED = "lifecycle_completed"
    LIFECYCLE_FAILED = "lifecycle_failed"
    LIFECYCLE_CANCELLED = "lifecycle_cancelled"
    TIMEOUT = "timeout"


class LifecycleStatus(str, Enum):
    """Overall status of a lifecycle.

    Tracks the high-level state of a lifecycle from creation
    through to its terminal state (completed, failed, cancelled,
    or timed_out).
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class StageExecution:
    """Record of a single stage execution within a lifecycle.

    Captures timing, outcome, and optional retry metadata for
    each processing stage as it runs.

    Attributes:
        stage:        Name of the pipeline stage (e.g. "rag_retrieval").
        status:       Outcome of the stage execution — one of
                      "started", "completed", "failed", "skipped".
        started_at:   ISO-8601 UTC timestamp when the stage began.
        completed_at: ISO-8601 UTC timestamp when the stage finished,
                      or None if still in progress.
        duration_ms:  Wall-clock duration in milliseconds.
        error:        Error message if the stage failed, else None.
        retry_count:  Number of retries attempted for this stage.
        metadata:     Arbitrary key-value data attached by the stage.
    """
    stage: str
    status: str  # started, completed, failed, skipped
    started_at: str  # ISO UTC
    completed_at: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleConfig:
    """Per-company lifecycle configuration.

    Controls timeout, retry behaviour, logging verbosity, and
    failure handling strategy for each tenant.

    Attributes:
        company_id:              Tenant identifier (BC-001).
        variant:                 Default PARWA variant for this company.
        timeout_seconds:         Maximum wall-clock time for a lifecycle.
        max_retries_per_stage:   How many times a failed stage may
                                 be retried before giving up.
        retry_delay_ms:          Delay between retries in milliseconds.
        enable_detailed_logging: If True, emit verbose stage-level logs.
        stages_to_skip:          Stage names to skip automatically
                                 (used for mini_parwa reduced pipeline).
        on_failure_action:       Strategy when a stage fails after all
                                 retries — "degrade", "fail_fast", or
                                 "retry_all".
    """
    company_id: str = ""
    variant: str = "parwa"
    timeout_seconds: float = 300.0  # 5 min default
    max_retries_per_stage: int = 2
    retry_delay_ms: int = 500
    enable_detailed_logging: bool = True
    stages_to_skip: List[str] = field(default_factory=list)
    on_failure_action: str = "degrade"  # degrade, fail_fast, retry_all


@dataclass
class LifecycleSnapshot:
    """Point-in-time snapshot of a lifecycle.

    Immutable view of a lifecycle's state at the moment it was
    captured. Used for history records and observability reporting.

    Attributes:
        lifecycle_id:      Unique identifier for the lifecycle.
        ticket_id:         Ticket being processed.
        company_id:        Tenant identifier (BC-001).
        variant:           PARWA variant in use.
        status:            Current LifecycleStatus value.
        current_stage:     Stage currently executing, or the terminal
                           stage if completed/failed/cancelled.
        completed_stages:  List of stages that finished successfully.
        failed_stages:     List of stages that failed.
        stage_executions:  Serialized list of StageExecution dicts.
        started_at:        ISO-8601 UTC when the lifecycle began.
        completed_at:      ISO-8601 UTC when the lifecycle ended,
                           or None if still active.
        total_duration_ms: Total wall-clock time in milliseconds.
        metadata:          Arbitrary metadata attached to the lifecycle.
    """
    lifecycle_id: str
    ticket_id: str
    company_id: str
    variant: str
    status: str
    current_stage: str
    completed_stages: List[str]
    failed_stages: List[str]
    stage_executions: List[Dict[str, Any]]
    started_at: str
    completed_at: Optional[str]
    total_duration_ms: int
    metadata: Dict[str, Any]


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════


# Ordered pipeline stages per PARWA variant.
# mini_parwa uses a reduced pipeline for faster response at lower cost.
_PIPELINE_STAGES: Dict[str, List[str]] = {
    "mini_parwa": [
        "signal_extraction",
        "intent_classification",
        "response_generation",
        "guardrails_check",
    ],
    "parwa": [
        "signal_extraction",
        "intent_classification",
        "rag_retrieval",
        "context_compression",
        "response_generation",
        "guardrails_check",
        "post_processing",
    ],
    "high_parwa": [
        "signal_extraction",
        "intent_classification",
        "rag_retrieval",
        "context_compression",
        "response_generation",
        "guardrails_check",
        "post_processing",
    ],
}

# Terminal stages — once a lifecycle reaches one of these,
# no further stage transitions are allowed.
_TERMINAL_STAGES: List[str] = [
    LifecycleStage.COMPLETED.value,
    LifecycleStage.FAILED.value,
    LifecycleStage.CANCELLED.value,
]

# Terminal lifecycle statuses.
_TERMINAL_STATUSES: List[str] = [
    LifecycleStatus.COMPLETED.value,
    LifecycleStatus.FAILED.value,
    LifecycleStatus.CANCELLED.value,
    LifecycleStatus.TIMED_OUT.value,
]

# Maximum number of active lifecycles tracked simultaneously.
_MAX_ACTIVE_LIFECYCLES: int = 10_000


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> str:
    """Return current UTC timestamp as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a new unique identifier (UUID4)."""
    return str(uuid.uuid4())


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string into a datetime.

    Handles both ``Z`` suffix and ``+00:00`` timezone notation.
    Returns None on any parse failure.

    Args:
        ts: ISO-8601 timestamp string.

    Returns:
        datetime object in UTC, or None if parsing fails.
    """
    if not ts:
        return None
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None


def _duration_ms(started_at: str, completed_at: Optional[str]) -> int:
    """Calculate the duration in milliseconds between two ISO timestamps.

    Args:
        started_at:   ISO-8601 start timestamp.
        completed_at: ISO-8601 end timestamp, or None (uses now).

    Returns:
        Duration in milliseconds (rounded to int). Returns 0 if
        either timestamp cannot be parsed.
    """
    start = _parse_iso(started_at)
    end = _parse_iso(completed_at) if completed_at else datetime.now(
        timezone.utc,
    )
    if start is None or end is None:
        return 0
    delta = (end - start).total_seconds()
    return max(0, int(delta * 1000))


def _is_valid_stage(stage: str, variant: str) -> bool:
    """Check if a stage name is valid for a given variant.

    Args:
        stage:   Stage name to validate.
        variant: PARWA variant identifier.

    Returns:
        True if the stage belongs to the variant's pipeline.
    """
    stages = _PIPELINE_STAGES.get(variant, _PIPELINE_STAGES["parwa"])
    return stage in stages


def _is_terminal_status(status: str) -> bool:
    """Check if a lifecycle status is a terminal (final) state.

    Args:
        status: LifecycleStatus value string.

    Returns:
        True if the status is terminal.
    """
    return status in _TERMINAL_STATUSES


def _stage_execution_to_dict(se: StageExecution) -> Dict[str, Any]:
    """Serialize a StageExecution to a plain dictionary.

    Args:
        se: StageExecution dataclass instance.

    Returns:
        Dictionary representation of the stage execution.
    """
    return {
        "stage": se.stage,
        "status": se.status,
        "started_at": se.started_at,
        "completed_at": se.completed_at,
        "duration_ms": se.duration_ms,
        "error": se.error,
        "retry_count": se.retry_count,
        "metadata": se.metadata,
    }


# ══════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ══════════════════════════════════════════════════════════════════


class CallLifecycleManager:
    """Execution Lifecycle Management for AI agent calls.

    Tracks the full lifecycle of a call/session through pipeline stages,
    manages transitions, retries, timeouts, and provides observability.

    Each lifecycle is scoped to a company (BC-001) and a ticket.
    Thread-safe via RLock for concurrent access in multi-threaded
    server environments.

    BC-001: company_id first parameter on all public methods.
    BC-008: Every public method wrapped in try/except — never crash.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        """Initialize the lifecycle manager with empty state."""
        self._lock = threading.RLock()
        # Active lifecycles: {lifecycle_id: lifecycle_data}
        self._lifecycles: Dict[str, Dict[str, Any]] = {}
        # Company configs: {company_id: LifecycleConfig}
        self._configs: Dict[str, LifecycleConfig] = {}
        # Lifecycle history: {company_id: [snapshot dicts]}
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Event listeners for lifecycle event dispatch
        self._listeners: List[Callable[..., None]] = []
        # Max history entries per company
        self._max_history: int = 500

    # ══════════════════════════════════════════════════════════
    # CONFIGURATION
    # ══════════════════════════════════════════════════════════

    def configure(
        self,
        company_id: str,
        config: LifecycleConfig,
    ) -> None:
        """Set per-company lifecycle configuration.

        Overrides any previously set configuration for the company.
        The config controls timeout, retries, logging, and failure
        handling strategy.

        Args:
            company_id: Tenant identifier (BC-001).
            config:     LifecycleConfig with desired settings. The
                        config's company_id field will be set
                        automatically to match the parameter.
        """
        try:
            with self._lock:
                config.company_id = company_id
                self._configs[company_id] = config
            logger.info(
                "lifecycle_configured",
                company_id=company_id,
                variant=config.variant,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries_per_stage,
                on_failure_action=config.on_failure_action,
            )
        except Exception:
            logger.exception(
                "lifecycle_configure_failed",
                company_id=company_id,
            )

    def get_config(self, company_id: str) -> LifecycleConfig:
        """Get lifecycle configuration for a company with defaults.

        If no custom configuration has been set, returns a default
        LifecycleConfig with sensible baseline values.

        Args:
            company_id: Tenant identifier.

        Returns:
            LifecycleConfig for the company (or a fresh default).
        """
        try:
            with self._lock:
                if company_id in self._configs:
                    return self._configs[company_id]
                default = LifecycleConfig(company_id=company_id)
                self._configs[company_id] = default
                return default
        except Exception:
            logger.exception(
                "lifecycle_get_config_failed",
                company_id=company_id,
            )
            return LifecycleConfig(company_id=company_id)

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE CREATION
    # ══════════════════════════════════════════════════════════

    def start_lifecycle(
        self,
        company_id: str,
        ticket_id: str,
        variant: str = "parwa",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Initialize a new lifecycle for a ticket and return its ID.

        Creates a new lifecycle tracked by a UUID4 identifier,
        sets its status to RUNNING, records the start time, and
        emits a LIFECYCLE_STARTED event.

        Args:
            company_id: Tenant identifier (BC-001).
            ticket_id:  Ticket being processed.
            variant:    PARWA variant (mini_parwa, parwa, high_parwa).
            metadata:   Optional arbitrary metadata to attach.

        Returns:
            The lifecycle_id (UUID string) if successful, or None
            if the lifecycle could not be created.
        """
        try:
            lifecycle_id = _new_id()
            now = _now_utc()
            stages = self.get_pipeline_stages(variant)
            config = self.get_config(company_id)

            lifecycle_data: Dict[str, Any] = {
                "id": lifecycle_id,
                "ticket_id": ticket_id,
                "company_id": company_id,
                "variant": variant,
                "status": LifecycleStatus.RUNNING.value,
                "current_stage": LifecycleStage.INITIALIZED.value,
                "stages": stages,
                "stage_executions": [],
                "started_at": now,
                "completed_at": None,
                "metadata": metadata or {},
                "event_log": [],
            }

            with self._lock:
                if len(self._lifecycles) >= _MAX_ACTIVE_LIFECYCLES:
                    # Evict oldest completed/failed lifecycles
                    self._evict_stale_lifecycles()
                self._lifecycles[lifecycle_id] = lifecycle_data

            self._emit_event(
                LifecycleEvent.LIFECYCLE_STARTED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "variant": variant,
                    "stages": stages,
                    "metadata": metadata or {},
                },
            )

            logger.info(
                "lifecycle_started",
                company_id=company_id,
                ticket_id=ticket_id,
                lifecycle_id=lifecycle_id,
                variant=variant,
                stage_count=len(stages),
            )
            return lifecycle_id

        except Exception:
            logger.exception(
                "lifecycle_start_failed",
                company_id=company_id,
                ticket_id=ticket_id,
                variant=variant,
            )
            return None

    # ══════════════════════════════════════════════════════════
    # STAGE TRANSITIONS
    # ══════════════════════════════════════════════════════════

    def start_stage(
        self,
        company_id: str,
        lifecycle_id: str,
        stage: str,
    ) -> bool:
        """Mark a pipeline stage as started within a lifecycle.

        Validates the stage against the variant's pipeline, checks
        timeout status, and creates a new StageExecution record.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.
            stage:        Stage name to start.

        Returns:
            True if the stage was successfully started, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                status = lc["status"]
                if _is_terminal_status(status):
                    logger.warning(
                        "start_stage_on_terminal_lifecycle",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        stage=stage,
                        status=status,
                    )
                    return False

                # Check timeout before proceeding
                timeout_info = self._check_timeout_inner(lc)
                if timeout_info["timed_out"]:
                    lc["status"] = LifecycleStatus.TIMED_OUT.value
                    lc["completed_at"] = _now_utc()
                    self._emit_event(
                        LifecycleEvent.TIMEOUT.value,
                        lifecycle_id,
                        timeout_info,
                    )
                    logger.warning(
                        "lifecycle_timed_out_on_stage_start",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        stage=stage,
                        elapsed_ms=timeout_info["elapsed_ms"],
                    )
                    return False

                variant = lc["variant"]
                if not _is_valid_stage(stage, variant):
                    logger.warning(
                        "start_stage_invalid_for_variant",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        stage=stage,
                        variant=variant,
                    )
                    return False

                # Create stage execution record
                stage_exec = StageExecution(
                    stage=stage,
                    status="started",
                    started_at=_now_utc(),
                )
                lc["stage_executions"].append(stage_exec)
                lc["current_stage"] = stage

                if lc.get("metadata"):
                    lc["metadata"]["current_stage"] = stage

            self._emit_event(
                LifecycleEvent.STAGE_STARTED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": lc["ticket_id"],
                    "stage": stage,
                    "variant": variant,
                },
            )

            logger.info(
                "stage_started",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
                variant=variant,
            )
            return True

        except Exception:
            logger.exception(
                "start_stage_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
            )
            return False

    def complete_stage(
        self,
        company_id: str,
        lifecycle_id: str,
        stage: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a pipeline stage as completed successfully.

        Updates the most recent StageExecution for the given stage
        with completion time and duration. Records the stage in
        the completed list.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.
            stage:        Stage name that completed.
            metadata:     Optional result metadata from the stage.

        Returns:
            True if the stage was completed, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                stage_exec = self._find_stage_execution(lc, stage)
                if stage_exec is None:
                    logger.warning(
                        "complete_stage_not_found",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        stage=stage,
                    )
                    return False

                now = _now_utc()
                stage_exec.status = "completed"
                stage_exec.completed_at = now
                stage_exec.duration_ms = _duration_ms(
                    stage_exec.started_at, now,
                )
                if metadata:
                    stage_exec.metadata.update(metadata)

            self._emit_event(
                LifecycleEvent.STAGE_COMPLETED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": lc["ticket_id"],
                    "stage": stage,
                    "duration_ms": stage_exec.duration_ms,
                },
            )

            logger.info(
                "stage_completed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
                duration_ms=stage_exec.duration_ms,
            )
            return True

        except Exception:
            logger.exception(
                "complete_stage_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
            )
            return False

    def fail_stage(
        self,
        company_id: str,
        lifecycle_id: str,
        stage: str,
        error: str,
        retry_count: int = 0,
    ) -> bool:
        """Mark a pipeline stage as failed, optionally scheduling retry.

        If the stage's retry count is below the per-company config
        maximum, emits a STAGE_RETRY event and keeps the lifecycle
        running. Otherwise, applies the configured failure action
        (degrade, fail_fast, or retry_all).

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.
            stage:        Stage name that failed.
            error:        Human-readable error description.
            retry_count:  Number of retries already attempted.

        Returns:
            True if the failure was recorded, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            config = self.get_config(company_id)

            with self._lock:
                stage_exec = self._find_stage_execution(lc, stage)
                if stage_exec is None:
                    logger.warning(
                        "fail_stage_not_found",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        stage=stage,
                    )
                    return False

                now = _now_utc()
                stage_exec.status = "failed"
                stage_exec.completed_at = now
                stage_exec.duration_ms = _duration_ms(
                    stage_exec.started_at, now,
                )
                stage_exec.error = error
                stage_exec.retry_count = retry_count

                # Check if retry is still possible
                can_retry = (
                    retry_count < config.max_retries_per_stage
                    and config.on_failure_action != "fail_fast"
                )

                if can_retry:
                    self._emit_event(
                        LifecycleEvent.STAGE_RETRY.value,
                        lifecycle_id,
                        {
                            "company_id": company_id,
                            "ticket_id": lc["ticket_id"],
                            "stage": stage,
                            "error": error,
                            "retry_count": retry_count,
                            "max_retries": config.max_retries_per_stage,
                            "retry_delay_ms": config.retry_delay_ms,
                        },
                    )
                    logger.warning(
                        "stage_failed_retry_eligible",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        stage=stage,
                        error=error[:200],
                        retry_count=retry_count,
                        max_retries=config.max_retries_per_stage,
                    )
                else:
                    # Retries exhausted — apply failure action
                    self._emit_event(
                        LifecycleEvent.STAGE_FAILED.value,
                        lifecycle_id,
                        {
                            "company_id": company_id,
                            "ticket_id": lc["ticket_id"],
                            "stage": stage,
                            "error": error,
                            "retry_count": retry_count,
                            "action": config.on_failure_action,
                        },
                    )

                    if config.on_failure_action == "fail_fast":
                        lc["status"] = LifecycleStatus.FAILED.value
                        lc["completed_at"] = _now_utc()
                        self._emit_event(
                            LifecycleEvent.LIFECYCLE_FAILED.value,
                            lifecycle_id,
                            {
                                "company_id": company_id,
                                "ticket_id": lc["ticket_id"],
                                "stage": stage,
                                "error": error,
                                "reason": "fail_fast",
                            },
                        )
                        logger.error(
                            "lifecycle_failed_fast",
                            company_id=company_id,
                            lifecycle_id=lifecycle_id,
                            stage=stage,
                            error=error[:200],
                        )
                    elif config.on_failure_action == "degrade":
                        logger.warning(
                            "stage_failed_degraded",
                            company_id=company_id,
                            lifecycle_id=lifecycle_id,
                            stage=stage,
                            error=error[:200],
                        )
                    else:
                        logger.warning(
                            "stage_failed_retry_all",
                            company_id=company_id,
                            lifecycle_id=lifecycle_id,
                            stage=stage,
                            error=error[:200],
                        )

            return True

        except Exception:
            logger.exception(
                "fail_stage_crashed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
            )
            return False

    def skip_stage(
        self,
        company_id: str,
        lifecycle_id: str,
        stage: str,
        reason: str = "",
    ) -> bool:
        """Skip a pipeline stage within a lifecycle.

        Records the skip with an optional reason. This is used when
        a variant's reduced pipeline omits certain stages, or when
        graceful degradation decides to bypass a non-critical stage.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.
            stage:        Stage name to skip.
            reason:       Human-readable reason for skipping.

        Returns:
            True if the stage was skipped, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                status = lc["status"]
                if _is_terminal_status(status):
                    return False

                now = _now_utc()
                stage_exec = StageExecution(
                    stage=stage,
                    status="skipped",
                    started_at=now,
                    completed_at=now,
                    duration_ms=0,
                    metadata={"skip_reason": reason},
                )
                lc["stage_executions"].append(stage_exec)

            self._emit_event(
                LifecycleEvent.STAGE_SKIPPED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": lc["ticket_id"],
                    "stage": stage,
                    "reason": reason,
                },
            )

            logger.info(
                "stage_skipped",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
                reason=reason,
            )
            return True

        except Exception:
            logger.exception(
                "skip_stage_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
            )
            return False

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE TERMINAL TRANSITIONS
    # ══════════════════════════════════════════════════════════

    def cancel_lifecycle(
        self,
        company_id: str,
        lifecycle_id: str,
        reason: str = "",
    ) -> bool:
        """Cancel an active lifecycle.

        Moves the lifecycle to CANCELLED status, records the
        completion time, archives the snapshot to history, and
        emits a LIFECYCLE_CANCELLED event.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.
            reason:       Human-readable cancellation reason.

        Returns:
            True if the lifecycle was cancelled, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                status = lc["status"]
                if _is_terminal_status(status):
                    logger.warning(
                        "cancel_lifecycle_already_terminal",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        status=status,
                    )
                    return False

                now = _now_utc()
                lc["status"] = LifecycleStatus.CANCELLED.value
                lc["completed_at"] = now
                lc["current_stage"] = LifecycleStage.CANCELLED.value
                lc["metadata"]["cancel_reason"] = reason

                # Archive snapshot
                snapshot = self._build_snapshot(lc)
                self._archive_snapshot(company_id, snapshot)
                # Remove from active lifecycles
                self._lifecycles.pop(lifecycle_id, None)

            self._emit_event(
                LifecycleEvent.LIFECYCLE_CANCELLED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": lc["ticket_id"],
                    "reason": reason,
                    "total_duration_ms": snapshot.total_duration_ms,
                },
            )

            logger.info(
                "lifecycle_cancelled",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                reason=reason,
            )
            return True

        except Exception:
            logger.exception(
                "cancel_lifecycle_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return False

    def complete_lifecycle(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> bool:
        """Mark a lifecycle as successfully completed.

        Moves the lifecycle to COMPLETED status, calculates total
        duration, archives the snapshot, and emits a
        LIFECYCLE_COMPLETED event.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            True if the lifecycle was completed, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                status = lc["status"]
                if _is_terminal_status(status):
                    logger.warning(
                        "complete_lifecycle_already_terminal",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        status=status,
                    )
                    return False

                now = _now_utc()
                lc["status"] = LifecycleStatus.COMPLETED.value
                lc["completed_at"] = now
                lc["current_stage"] = LifecycleStage.COMPLETED.value

                # Archive snapshot
                snapshot = self._build_snapshot(lc)
                self._archive_snapshot(company_id, snapshot)
                # Remove from active lifecycles
                self._lifecycles.pop(lifecycle_id, None)

            self._emit_event(
                LifecycleEvent.LIFECYCLE_COMPLETED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": lc["ticket_id"],
                    "variant": lc["variant"],
                    "total_duration_ms": snapshot.total_duration_ms,
                    "completed_stages": snapshot.completed_stages,
                    "failed_stages": snapshot.failed_stages,
                },
            )

            logger.info(
                "lifecycle_completed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                ticket_id=lc["ticket_id"],
                variant=lc["variant"],
                duration_ms=snapshot.total_duration_ms,
            )
            return True

        except Exception:
            logger.exception(
                "complete_lifecycle_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return False

    def fail_lifecycle(
        self,
        company_id: str,
        lifecycle_id: str,
        error: str,
    ) -> bool:
        """Mark a lifecycle as failed.

        Moves the lifecycle to FAILED status, records the error,
        archives the snapshot, and emits a LIFECYCLE_FAILED event.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.
            error:        Human-readable error description.

        Returns:
            True if the lifecycle was marked as failed, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                status = lc["status"]
                if _is_terminal_status(status):
                    logger.warning(
                        "fail_lifecycle_already_terminal",
                        company_id=company_id,
                        lifecycle_id=lifecycle_id,
                        status=status,
                    )
                    return False

                now = _now_utc()
                lc["status"] = LifecycleStatus.FAILED.value
                lc["completed_at"] = now
                lc["current_stage"] = LifecycleStage.FAILED.value
                lc["metadata"]["failure_error"] = error

                # Archive snapshot
                snapshot = self._build_snapshot(lc)
                self._archive_snapshot(company_id, snapshot)
                # Remove from active lifecycles
                self._lifecycles.pop(lifecycle_id, None)

            self._emit_event(
                LifecycleEvent.LIFECYCLE_FAILED.value,
                lifecycle_id,
                {
                    "company_id": company_id,
                    "ticket_id": lc["ticket_id"],
                    "variant": lc["variant"],
                    "error": error,
                    "total_duration_ms": snapshot.total_duration_ms,
                },
            )

            logger.error(
                "lifecycle_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                ticket_id=lc["ticket_id"],
                error=error[:300],
                duration_ms=snapshot.total_duration_ms,
            )
            return True

        except Exception:
            logger.exception(
                "fail_lifecycle_crashed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return False

    # ══════════════════════════════════════════════════════════
    # QUERY METHODS
    # ══════════════════════════════════════════════════════════

    def get_lifecycle(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the current lifecycle data as a snapshot dict.

        Returns a point-in-time snapshot containing status, stage
        executions, timing, and metadata.

        Args:
            company_id:   Tenant identifier (BC-001).
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            Snapshot dictionary, or None if not found or not owned
            by the given company.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return None

            with self._lock:
                snapshot = self._build_snapshot(lc)
                return self._snapshot_to_dict(snapshot)

        except Exception:
            logger.exception(
                "get_lifecycle_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return None

    def get_active_lifecycles(
        self,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """List all active (non-terminal) lifecycles for a company.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of lifecycle snapshot dicts currently in progress.
        """
        try:
            result: List[Dict[str, Any]] = []
            with self._lock:
                for lc_id, lc in self._lifecycles.items():
                    if lc.get("company_id") == company_id:
                        if not _is_terminal_status(lc.get("status", "")):
                            snapshot = self._build_snapshot(lc)
                            result.append(self._snapshot_to_dict(snapshot))
            return result

        except Exception:
            logger.exception(
                "get_active_lifecycles_failed",
                company_id=company_id,
            )
            return []

    def get_lifecycle_history(
        self,
        company_id: str,
        ticket_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get past lifecycle snapshots for a company, optionally
        filtered by ticket.

        Returns completed, failed, and cancelled lifecycle snapshots
        from the history store. Results are ordered most-recent-first.

        Args:
            company_id: Tenant identifier.
            ticket_id:  Optional ticket filter. If None, returns all
                        lifecycles for the company.
            limit:      Maximum number of snapshots to return.

        Returns:
            List of snapshot dicts from history.
        """
        try:
            with self._lock:
                history = self._history.get(company_id, [])
                if ticket_id:
                    filtered = [
                        s for s in history
                        if s.get("ticket_id") == ticket_id
                    ]
                else:
                    filtered = list(history)

                # Return most-recent-first, limited
                return list(reversed(filtered[-limit:]))

        except Exception:
            logger.exception(
                "get_lifecycle_history_failed",
                company_id=company_id,
                ticket_id=ticket_id,
            )
            return []

    def get_stage_duration(
        self,
        company_id: str,
        lifecycle_id: str,
        stage: str,
    ) -> int:
        """Get the duration of a specific stage execution in
        milliseconds.

        Looks up the most recent StageExecution record for the
        given stage and returns its duration. Returns 0 if the
        stage hasn't completed or wasn't found.

        Args:
            company_id:   Tenant identifier.
            lifecycle_id: Unique lifecycle identifier.
            stage:        Stage name to look up.

        Returns:
            Duration in milliseconds, or 0 if not available.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return 0

            with self._lock:
                stage_exec = self._find_stage_execution(lc, stage)
                if stage_exec is not None and stage_exec.duration_ms > 0:
                    return stage_exec.duration_ms

                # If stage is in "started" status, compute live duration
                if stage_exec is not None and stage_exec.status == "started":
                    return _duration_ms(stage_exec.started_at, None)

            return 0

        except Exception:
            logger.exception(
                "get_stage_duration_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
                stage=stage,
            )
            return 0

    def get_total_duration(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> int:
        """Get the total duration of a lifecycle in milliseconds.

        For completed lifecycles, returns the recorded total. For
        active lifecycles, computes from start to now.

        Args:
            company_id:   Tenant identifier.
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            Total duration in milliseconds, or 0 if not found.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return 0

            with self._lock:
                return _duration_ms(
                    lc["started_at"], lc["completed_at"],
                )

        except Exception:
            logger.exception(
                "get_total_duration_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return 0

    def is_lifecycle_active(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> bool:
        """Check if a lifecycle is currently running (not terminal).

        Args:
            company_id:   Tenant identifier.
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            True if the lifecycle exists and is in a non-terminal
            status, False otherwise.
        """
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return False

            with self._lock:
                return not _is_terminal_status(lc.get("status", ""))

        except Exception:
            logger.exception(
                "is_lifecycle_active_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return False

    def get_timeout_status(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> Dict[str, Any]:
        """Check if a lifecycle has exceeded its configured timeout.

        Computes the elapsed time since the lifecycle started and
        compares against the per-company timeout configuration.

        Args:
            company_id:   Tenant identifier.
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            Dict with keys:
            - ``timed_out`` (bool): Whether the timeout has been hit.
            - ``elapsed_ms`` (int): Milliseconds since start.
            - ``timeout_ms`` (int): Configured timeout in milliseconds.
            - ``remaining_ms`` (int): Milliseconds until timeout, or
              0 if already timed out.
        """
        default_result: Dict[str, Any] = {
            "timed_out": False,
            "elapsed_ms": 0,
            "timeout_ms": 0,
            "remaining_ms": 0,
        }
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return default_result

            config = self.get_config(company_id)

            with self._lock:
                return self._check_timeout_inner(lc, config)

        except Exception:
            logger.exception(
                "get_timeout_status_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return default_result

    # ══════════════════════════════════════════════════════════
    # PIPELINE STAGES
    # ══════════════════════════════════════════════════════════

    def get_pipeline_stages(self, variant: str) -> List[str]:
        """Return the ordered list of pipeline stages for a variant.

        Args:
            variant: PARWA variant (mini_parwa, parwa, high_parwa).

        Returns:
            Ordered list of stage name strings.
        """
        try:
            return list(
                _PIPELINE_STAGES.get(variant, _PIPELINE_STAGES["parwa"]),
            )
        except Exception:
            logger.exception("get_pipeline_stages_failed", variant=variant)
            return list(_PIPELINE_STAGES["parwa"])

    # ══════════════════════════════════════════════════════════
    # SUMMARY & STATISTICS
    # ══════════════════════════════════════════════════════════

    def get_lifecycle_summary(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> Dict[str, Any]:
        """Get a rich summary dict for a single lifecycle.

        Includes lifecycle metadata, per-stage breakdown, timing
        info, and an overall assessment.

        Args:
            company_id:   Tenant identifier.
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            Summary dictionary with lifecycle details, or an empty
            dict if not found.
        """
        empty: Dict[str, Any] = {}
        try:
            lc = self._get_lifecycle_or_error(company_id, lifecycle_id)
            if lc is None:
                return empty

            with self._lock:
                total_ms = _duration_ms(
                    lc["started_at"], lc["completed_at"],
                )
                completed = []
                failed = []
                skipped = []
                stage_breakdown: List[Dict[str, Any]] = []

                for se in lc["stage_executions"]:
                    se_dict = _stage_execution_to_dict(se)
                    stage_breakdown.append(se_dict)
                    if se.status == "completed":
                        completed.append(se.stage)
                    elif se.status == "failed":
                        failed.append(se.stage)
                    elif se.status == "skipped":
                        skipped.append(se.stage)

                # Calculate stage-level timing stats
                stage_timing: Dict[str, int] = {}
                for se in lc["stage_executions"]:
                    if se.duration_ms > 0:
                        stage_timing[se.stage] = se.duration_ms

                # Identify slowest stage
                slowest_stage = ""
                slowest_ms = 0
                for stage_name, dur in stage_timing.items():
                    if dur > slowest_ms:
                        slowest_ms = dur
                        slowest_stage = stage_name

                return {
                    "lifecycle_id": lc["id"],
                    "ticket_id": lc["ticket_id"],
                    "company_id": lc["company_id"],
                    "variant": lc["variant"],
                    "status": lc["status"],
                    "started_at": lc["started_at"],
                    "completed_at": lc["completed_at"],
                    "total_duration_ms": total_ms,
                    "total_stages": len(lc["stages"]),
                    "completed_stages": completed,
                    "failed_stages": failed,
                    "skipped_stages": skipped,
                    "current_stage": lc["current_stage"],
                    "stage_timing": stage_timing,
                    "slowest_stage": slowest_stage,
                    "slowest_stage_ms": slowest_ms,
                    "stage_breakdown": stage_breakdown,
                    "metadata": lc["metadata"],
                    "timeout_status": self._check_timeout_inner(lc),
                }

        except Exception:
            logger.exception(
                "get_lifecycle_summary_failed",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return empty

    def get_statistics(self, company_id: str) -> Dict[str, Any]:
        """Get aggregated lifecycle statistics for a company.

        Computes totals, success/failure rates, average durations,
        per-stage failure rates, and variant distribution from both
        active lifecycles and history.

        Args:
            company_id: Tenant identifier.

        Returns:
            Statistics dictionary.
        """
        default_stats: Dict[str, Any] = {
            "company_id": company_id,
            "total_lifecycles": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "active": 0,
            "timed_out": 0,
            "success_rate": 0.0,
            "avg_duration_ms": 0,
            "p50_duration_ms": 0,
            "p95_duration_ms": 0,
            "stage_failure_rates": {},
            "variant_distribution": {},
        }
        try:
            with self._lock:
                # Gather all snapshots (active + history)
                all_snapshots: List[Dict[str, Any]] = []

                # Active lifecycles
                for lc_id, lc in self._lifecycles.items():
                    if lc.get("company_id") == company_id:
                        snapshot = self._build_snapshot(lc)
                        all_snapshots.append(
                            self._snapshot_to_dict(snapshot),
                        )

                # History
                history = self._history.get(company_id, [])
                all_snapshots.extend(history)

                if not all_snapshots:
                    return default_stats

                total = len(all_snapshots)
                completed = sum(
                    1 for s in all_snapshots
                    if s.get("status") == LifecycleStatus.COMPLETED.value
                )
                failed = sum(
                    1 for s in all_snapshots
                    if s.get("status") == LifecycleStatus.FAILED.value
                )
                cancelled = sum(
                    1 for s in all_snapshots
                    if s.get("status") == LifecycleStatus.CANCELLED.value
                )
                active = sum(
                    1 for s in all_snapshots
                    if s.get("status") == LifecycleStatus.RUNNING.value
                )
                timed_out = sum(
                    1 for s in all_snapshots
                    if s.get("status") == LifecycleStatus.TIMED_OUT.value
                )

                # Duration stats (only from finished lifecycles)
                finished_durations = [
                    s["total_duration_ms"]
                    for s in all_snapshots
                    if s.get("total_duration_ms", 0) > 0
                ]
                avg_duration = 0
                p50_duration = 0
                p95_duration = 0

                if finished_durations:
                    finished_durations.sort()
                    avg_duration = int(
                        sum(finished_durations) / len(finished_durations),
                    )
                    p50_idx = len(finished_durations) // 2
                    p50_duration = finished_durations[p50_idx]
                    p95_idx = int(len(finished_durations) * 0.95)
                    p95_idx = min(p95_idx, len(finished_durations) - 1)
                    p95_duration = finished_durations[p95_idx]

                # Stage failure rates
                stage_failures: Dict[str, int] = defaultdict(int)
                stage_totals: Dict[str, int] = defaultdict(int)
                for s in all_snapshots:
                    for se in s.get("stage_executions", []):
                        stage_name = se.get("stage", "")
                        stage_totals[stage_name] += 1
                        if se.get("status") == "failed":
                            stage_failures[stage_name] += 1

                failure_rates: Dict[str, float] = {}
                for stage_name, total_count in stage_totals.items():
                    if total_count > 0:
                        rate = (
                            stage_failures[stage_name] / total_count
                        ) * 100
                        failure_rates[stage_name] = round(rate, 2)

                # Variant distribution
                variant_dist: Dict[str, int] = defaultdict(int)
                for s in all_snapshots:
                    variant_dist[s.get("variant", "parwa")] += 1

                success_rate = (
                    (completed / total) * 100 if total > 0 else 0.0
                )

                return {
                    "company_id": company_id,
                    "total_lifecycles": total,
                    "completed": completed,
                    "failed": failed,
                    "cancelled": cancelled,
                    "active": active,
                    "timed_out": timed_out,
                    "success_rate": round(success_rate, 2),
                    "avg_duration_ms": avg_duration,
                    "p50_duration_ms": p50_duration,
                    "p95_duration_ms": p95_duration,
                    "stage_failure_rates": failure_rates,
                    "variant_distribution": dict(variant_dist),
                }

        except Exception:
            logger.exception(
                "get_statistics_failed",
                company_id=company_id,
            )
            return default_stats

    # ══════════════════════════════════════════════════════════
    # EVENT LISTENERS
    # ══════════════════════════════════════════════════════════

    def add_event_listener(self, callback: Callable[..., None]) -> None:
        """Register a callback for lifecycle events.

        The callback will be invoked with two arguments:
        ``(event_type: str, data: Dict[str, Any])``.

        Listeners must not raise exceptions; any exception from a
        listener is caught and logged to prevent cascading failures.

        Args:
            callback: A callable accepting event_type and data dict.
        """
        try:
            with self._lock:
                if callback not in self._listeners:
                    self._listeners.append(callback)
            logger.info(
                "lifecycle_listener_added",
                listener=getattr(callback, "__name__", repr(callback)),
            )
        except Exception:
            logger.exception("add_event_listener_failed")

    def remove_event_listener(self, callback: Callable[..., None]) -> None:
        """Remove a previously registered lifecycle event listener.

        Args:
            callback: The callable to remove.
        """
        try:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)
            logger.info(
                "lifecycle_listener_removed",
                listener=getattr(callback, "__name__", repr(callback)),
            )
        except Exception:
            logger.exception("remove_event_listener_failed")

    # ══════════════════════════════════════════════════════════
    # DATA MANAGEMENT
    # ══════════════════════════════════════════════════════════

    def clear_company_data(self, company_id: str) -> bool:
        """Clear all data for a company (lifecycles, config, history).

        Removes all active lifecycles, custom configuration, and
        historical snapshots for the specified company.

        Args:
            company_id: Tenant identifier.

        Returns:
            True if data was cleared successfully, False otherwise.
        """
        try:
            with self._lock:
                # Remove active lifecycles belonging to this company
                to_remove = [
                    lid for lid, lc in self._lifecycles.items()
                    if lc.get("company_id") == company_id
                ]
                for lid in to_remove:
                    self._lifecycles.pop(lid, None)

                # Remove config
                self._configs.pop(company_id, None)

                # Remove history
                self._history.pop(company_id, None)

            logger.info(
                "lifecycle_company_data_cleared",
                company_id=company_id,
                removed_lifecycles=len(to_remove),
            )
            return True

        except Exception:
            logger.exception(
                "clear_company_data_failed",
                company_id=company_id,
            )
            return False

    # ══════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════

    def _emit_event(
        self,
        event_type: str,
        lifecycle_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Dispatch a lifecycle event to all registered listeners.

        Each listener is invoked with the event_type and data dict.
        Listener exceptions are caught and logged to prevent
        cascading failures (BC-008).

        Args:
            event_type:   LifecycleEvent value string.
            lifecycle_id: Associated lifecycle identifier.
            data:         Event payload dictionary.
        """
        for listener in self._listeners:
            try:
                listener(event_type, lifecycle_id, data)
            except Exception as exc:
                logger.error(
                    "lifecycle_event_listener_error",
                    event_type=event_type,
                    lifecycle_id=lifecycle_id,
                    listener=getattr(listener, "__name__", "unknown"),
                    error=str(exc),
                )

    def _get_lifecycle_or_error(
        self,
        company_id: str,
        lifecycle_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a lifecycle by ID and verify company ownership.

        Args:
            company_id:   Expected tenant identifier.
            lifecycle_id: Unique lifecycle identifier.

        Returns:
            Lifecycle data dict if found and company matches,
            None otherwise.
        """
        lc = self._lifecycles.get(lifecycle_id)
        if lc is None:
            logger.warning(
                "lifecycle_not_found",
                company_id=company_id,
                lifecycle_id=lifecycle_id,
            )
            return None
        if lc.get("company_id") != company_id:
            logger.warning(
                "lifecycle_company_mismatch",
                expected_company=company_id,
                actual_company=lc.get("company_id"),
                lifecycle_id=lifecycle_id,
            )
            return None
        return lc

    def _find_stage_execution(
        self,
        lc: Dict[str, Any],
        stage: str,
    ) -> Optional[StageExecution]:
        """Find the most recent StageExecution for a given stage.

        Searches the lifecycle's stage_executions list in reverse
        order to find the latest record for the stage.

        Args:
            lc:    Lifecycle data dict.
            stage: Stage name to search for.

        Returns:
            StageExecution if found, None otherwise.
        """
        for se in reversed(lc.get("stage_executions", [])):
            if se.stage == stage:
                return se
        return None

    def _build_snapshot(self, lc: Dict[str, Any]) -> LifecycleSnapshot:
        """Build a LifecycleSnapshot from a lifecycle data dict.

        Computes completed/failed stage lists and total duration.

        Args:
            lc: Lifecycle data dict.

        Returns:
            LifecycleSnapshot instance.
        """
        completed_stages: List[str] = []
        failed_stages: List[str] = []
        stage_exec_dicts: List[Dict[str, Any]] = []

        for se in lc.get("stage_executions", []):
            se_dict = _stage_execution_to_dict(se)
            stage_exec_dicts.append(se_dict)
            if se.status == "completed":
                completed_stages.append(se.stage)
            elif se.status == "failed":
                failed_stages.append(se.stage)

        total_ms = _duration_ms(lc["started_at"], lc["completed_at"])

        return LifecycleSnapshot(
            lifecycle_id=lc["id"],
            ticket_id=lc["ticket_id"],
            company_id=lc["company_id"],
            variant=lc["variant"],
            status=lc["status"],
            current_stage=lc["current_stage"],
            completed_stages=completed_stages,
            failed_stages=failed_stages,
            stage_executions=stage_exec_dicts,
            started_at=lc["started_at"],
            completed_at=lc["completed_at"],
            total_duration_ms=total_ms,
            metadata=lc["metadata"],
        )

    def _snapshot_to_dict(
        self, snapshot: LifecycleSnapshot,
    ) -> Dict[str, Any]:
        """Serialize a LifecycleSnapshot to a plain dictionary.

        Args:
            snapshot: LifecycleSnapshot instance.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "lifecycle_id": snapshot.lifecycle_id,
            "ticket_id": snapshot.ticket_id,
            "company_id": snapshot.company_id,
            "variant": snapshot.variant,
            "status": snapshot.status,
            "current_stage": snapshot.current_stage,
            "completed_stages": snapshot.completed_stages,
            "failed_stages": snapshot.failed_stages,
            "stage_executions": snapshot.stage_executions,
            "started_at": snapshot.started_at,
            "completed_at": snapshot.completed_at,
            "total_duration_ms": snapshot.total_duration_ms,
            "metadata": snapshot.metadata,
        }

    def _archive_snapshot(
        self,
        company_id: str,
        snapshot: LifecycleSnapshot,
    ) -> None:
        """Archive a lifecycle snapshot into the company's history.

        Appends to the history list and enforces the max history
        limit by trimming the oldest entries.

        Args:
            company_id: Tenant identifier.
            snapshot:   LifecycleSnapshot to archive.
        """
        snapshot_dict = self._snapshot_to_dict(snapshot)
        history = self._history[company_id]
        history.append(snapshot_dict)
        if len(history) > self._max_history:
            self._history[company_id] = history[-self._max_history:]

    def _check_timeout_inner(
        self,
        lc: Dict[str, Any],
        config: Optional[LifecycleConfig] = None,
    ) -> Dict[str, Any]:
        """Check timeout for a lifecycle (called under lock).

        Args:
            lc:     Lifecycle data dict.
            config: Optional LifecycleConfig. If None, fetched from
                    company_id in the lifecycle.

        Returns:
            Dict with timed_out, elapsed_ms, timeout_ms, remaining_ms.
        """
        timeout_s = (
            config.timeout_seconds
            if config
            else self.get_config(lc.get("company_id", "")).timeout_seconds
        )
        timeout_ms = int(timeout_s * 1000)
        elapsed_ms = _duration_ms(lc["started_at"], None)
        timed_out = elapsed_ms > timeout_ms
        remaining_ms = max(0, timeout_ms - elapsed_ms)

        return {
            "timed_out": timed_out,
            "elapsed_ms": elapsed_ms,
            "timeout_ms": timeout_ms,
            "remaining_ms": remaining_ms,
        }

    def _evict_stale_lifecycles(self) -> int:
        """Evict terminal lifecycles when active count exceeds limit.

        Removes completed, failed, and cancelled lifecycles
        oldest-first to free up space. Lifecycles are archived
        before eviction.

        Returns:
            Number of lifecycles evicted.
        """
        evicted = 0
        terminal_ids: List[str] = []

        for lid, lc in self._lifecycles.items():
            if _is_terminal_status(lc.get("status", "")):
                terminal_ids.append(lid)

        # Sort by completed_at (oldest first)
        terminal_ids.sort(
            key=lambda lid: self._lifecycles[lid].get(
                "completed_at", "",
            ) or "",
        )

        # Evict up to 25% of max capacity
        to_evict = max(
            1,
            len(self._lifecycles) - int(_MAX_ACTIVE_LIFECYCLES * 0.75),
        )

        for lid in terminal_ids[:to_evict]:
            lc = self._lifecycles.pop(lid, None)
            if lc:
                snapshot = self._build_snapshot(lc)
                self._archive_snapshot(lc["company_id"], snapshot)
                evicted += 1

        if evicted > 0:
            logger.info(
                "lifecycle_evicted_stale",
                evicted_count=evicted,
                remaining_active=len(self._lifecycles),
            )

        return evicted
