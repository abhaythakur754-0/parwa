"""
Technique Performance Metrics Pipeline (SG-16)

Wires technique execution metrics into the execution pipeline so every
technique execution is automatically logged.

Provides:
- MetricsRecord dataclass for structured log entries
- LogSink base class and concrete implementations (StdoutLogSink, InMemoryLogSink)
- MetricsPipeline class for recording and aggregating technique metrics

BC-001: All data scoped by company_id (tenant isolation).
BC-008: Never crashes — wraps everything in try/except.
Thread-safe with threading.Lock.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.technique_metrics import TechniqueMetricsCollector
from app.logger import get_logger

logger = get_logger("technique_metrics_pipeline")


# ── Data Structures ────────────────────────────────────────────────


@dataclass
class MetricsRecord:
    """Structured log entry for a single technique execution."""

    technique_id: str
    trigger_signal: str
    input_hash: str
    token_cost: int
    latency_ms: float
    output_quality_score: float
    variant_id: str
    tenant_id: str
    timestamp: float = field(default_factory=time.time)
    status: str = "success"


# ── Sink Base Class ────────────────────────────────────────────────


class LogSink(ABC):
    """Abstract base class for metrics log sinks."""

    @abstractmethod
    def emit(self, data: MetricsRecord) -> None:
        """Emit a MetricsRecord to the sink.

        Args:
            data: The metrics record to emit.
        """
        ...


class StdoutLogSink(LogSink):
    """Logs MetricsRecord to the app logger (stdout)."""

    def emit(self, data: MetricsRecord) -> None:
        """Log the metrics record via app.logger."""
        try:
            logger.info(
                "technique_execution_recorded",
                technique_id=data.technique_id,
                trigger_signal=data.trigger_signal,
                input_hash=data.input_hash,
                token_cost=data.token_cost,
                latency_ms=data.latency_ms,
                output_quality_score=data.output_quality_score,
                variant_id=data.variant_id,
                tenant_id=data.tenant_id,
                timestamp=data.timestamp,
                status=data.status,
            )
        except Exception:
            # BC-008: never crash
            pass


class InMemoryLogSink(LogSink):
    """Stores MetricsRecords in an in-memory list (for testing)."""

    def __init__(self) -> None:
        self._records: List[MetricsRecord] = []
        self._lock = threading.Lock()

    def emit(self, data: MetricsRecord) -> None:
        """Store the metrics record in memory."""
        try:
            with self._lock:
                self._records.append(data)
        except Exception:
            # BC-008: never crash
            pass

    def get_records(self) -> List[MetricsRecord]:
        """Return a copy of all stored records."""
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        """Clear all stored records."""
        with self._lock:
            self._records.clear()

    @property
    def record_count(self) -> int:
        """Return the number of stored records."""
        with self._lock:
            return len(self._records)


# ── Metrics Pipeline ───────────────────────────────────────────────


class MetricsPipeline:
    """
    Pipeline for recording and aggregating technique execution metrics.

    Provides a single entry point `record_technique_execution()` that:
    1. Creates a structured MetricsRecord
    2. Records in TechniqueMetricsCollector
    3. Emits to all configured sinks

    BC-001: All data scoped by company_id.
    BC-008: Never crashes.
    Thread-safe with threading.Lock.
    """

    def __init__(
        self,
        collector: Optional[TechniqueMetricsCollector] = None,
        sinks: Optional[List[LogSink]] = None,
    ) -> None:
        """
        Initialize the metrics pipeline.

        Args:
            collector: TechniqueMetricsCollector instance.
                If None, creates a new one.
            sinks: List of LogSink instances to emit records to.
                If None, creates a default StdoutLogSink.
        """
        self._collector = collector or TechniqueMetricsCollector()
        self._sinks: List[LogSink] = sinks if sinks is not None else [StdoutLogSink()]
        self._lock = threading.Lock()

        # In-memory storage for MetricsRecords by company_id
        self._company_records: Dict[str, List[MetricsRecord]] = {}

    @property
    def collector(self) -> TechniqueMetricsCollector:
        """Return the underlying TechniqueMetricsCollector."""
        return self._collector

    @property
    def sinks(self) -> List[LogSink]:
        """Return the list of configured sinks."""
        return list(self._sinks)

    def add_sink(self, sink: LogSink) -> None:
        """Add a new sink to the pipeline.

        Args:
            sink: LogSink instance to add.
        """
        try:
            with self._lock:
                self._sinks.append(sink)
        except Exception:
            # BC-008: never crash
            pass

    def record_technique_execution(
        self,
        technique_id: str,
        variant_id: str = "parwa",
        tenant_id: str = "default",
        trigger_signal: str = "unknown",
        input_hash: str = "",
        token_cost: int = 0,
        latency_ms: float = 0.0,
        output_quality_score: float = 0.0,
        status: str = "success",
    ) -> Optional[MetricsRecord]:
        """
        Record a single technique execution.

        Creates a MetricsRecord, records in TechniqueMetricsCollector,
        and emits to all configured sinks.

        BC-008: Returns None on error, never raises.

        Args:
            technique_id: Technique identifier (e.g. 'clara').
            variant_id: Execution variant (mini_parwa, parwa, parwa_high).
            tenant_id: Tenant company identifier (BC-001).
            trigger_signal: Signal that triggered this execution.
            input_hash: Hash of the input data.
            token_cost: Number of tokens consumed.
            latency_ms: Execution time in milliseconds.
            output_quality_score: Quality score of the output (0.0-1.0).
            status: Execution status (success, failure, timeout, error).

        Returns:
            MetricsRecord if successful, None on error.
        """
        try:
            # 1. Create structured log entry
            record = MetricsRecord(
                technique_id=technique_id,
                trigger_signal=trigger_signal,
                input_hash=input_hash,
                token_cost=token_cost,
                latency_ms=latency_ms,
                output_quality_score=output_quality_score,
                variant_id=variant_id,
                tenant_id=tenant_id,
                status=status,
            )

            # 2. Record in TechniqueMetricsCollector
            self._collector.record_execution(
                technique_id=technique_id,
                variant=variant_id,
                company_id=tenant_id,
                status=status,
                tokens_used=token_cost,
                exec_time_ms=latency_ms,
            )

            # 3. Store in company-scoped records
            with self._lock:
                if tenant_id not in self._company_records:
                    self._company_records[tenant_id] = []
                self._company_records[tenant_id].append(record)

            # 4. Emit to all sinks
            for sink in self._sinks:
                try:
                    sink.emit(record)
                except Exception:
                    # BC-008: individual sink failure doesn't stop others
                    pass

            return record

        except Exception:
            # BC-008: never crash
            return None

    def get_metrics_summary(
        self,
        company_id: str,
        time_window: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics summary for a company.

        BC-001: Scoped by company_id.
        BC-008: Returns empty dict on error.

        Args:
            company_id: Tenant company identifier.
            time_window: Optional time window for metrics
                (e.g. '1min', '5min', '15min', '1hr').
                If None, returns all-time metrics.

        Returns:
            Dict with aggregated stats including:
            - total_executions
            - success_count
            - failure_count
            - total_token_cost
            - avg_latency_ms
            - avg_quality_score
            - techniques: dict of per-technique stats
        """
        try:
            records = self._get_company_records(
                company_id, time_window,
            )

            if not records:
                return {
                    "company_id": company_id,
                    "total_executions": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "timeout_count": 0,
                    "error_count": 0,
                    "total_token_cost": 0,
                    "avg_latency_ms": 0.0,
                    "avg_quality_score": 0.0,
                    "techniques": {},
                }

            total = len(records)
            success = sum(1 for r in records if r.status == "success")
            failure = sum(1 for r in records if r.status == "failure")
            timeout = sum(1 for r in records if r.status == "timeout")
            error = sum(1 for r in records if r.status == "error")
            total_tokens = sum(r.token_cost for r in records)
            total_latency = sum(r.latency_ms for r in records)
            total_quality = sum(r.output_quality_score for r in records)

            # Per-technique breakdown
            techniques: Dict[str, Dict[str, Any]] = {}
            for r in records:
                if r.technique_id not in techniques:
                    techniques[r.technique_id] = {
                        "total": 0,
                        "success": 0,
                        "failure": 0,
                        "total_token_cost": 0,
                        "avg_latency_ms": 0.0,
                        "avg_quality_score": 0.0,
                    }
                t = techniques[r.technique_id]
                t["total"] += 1
                t["success"] += 1 if r.status == "success" else 0
                t["failure"] += 1 if r.status == "failure" else 0
                t["total_token_cost"] += r.token_cost

            # Compute averages for per-technique stats
            for tid, t in techniques.items():
                technique_records = [
                    r for r in records if r.technique_id == tid
                ]
                t["avg_latency_ms"] = (
                    sum(r.latency_ms for r in technique_records)
                    / len(technique_records)
                    if technique_records
                    else 0.0
                )
                t["avg_quality_score"] = (
                    sum(
                        r.output_quality_score
                        for r in technique_records
                    )
                    / len(technique_records)
                    if technique_records
                    else 0.0
                )

            return {
                "company_id": company_id,
                "total_executions": total,
                "success_count": success,
                "failure_count": failure,
                "timeout_count": timeout,
                "error_count": error,
                "total_token_cost": total_tokens,
                "avg_latency_ms": round(total_latency / total, 2),
                "avg_quality_score": round(
                    total_quality / total, 2,
                ),
                "techniques": techniques,
            }

        except Exception:
            # BC-008: never crash
            return {
                "company_id": company_id,
                "total_executions": 0,
                "success_count": 0,
                "failure_count": 0,
                "timeout_count": 0,
                "error_count": 0,
                "total_token_cost": 0,
                "avg_latency_ms": 0.0,
                "avg_quality_score": 0.0,
                "techniques": {},
            }

    def _get_company_records(
        self,
        company_id: str,
        time_window: Optional[str] = None,
    ) -> List[MetricsRecord]:
        """Get records for a company, optionally filtered by time window."""
        with self._lock:
            records = list(
                self._company_records.get(company_id, [])
            )

        if time_window is None:
            return records

        # Time window filtering
        window_seconds_map = {
            "1min": 60,
            "5min": 300,
            "15min": 900,
            "1hr": 3600,
        }
        window_seconds = window_seconds_map.get(time_window, 300)
        cutoff = time.time() - window_seconds

        return [r for r in records if r.timestamp >= cutoff]

    def get_company_record_count(self, company_id: str) -> int:
        """Get the number of records for a specific company.

        Args:
            company_id: Tenant company identifier.

        Returns:
            Number of records stored for the company.
        """
        try:
            with self._lock:
                return len(
                    self._company_records.get(company_id, [])
                )
        except Exception:
            return 0

    def reset_company_metrics(self, company_id: str) -> int:
        """Reset all metrics for a specific company.

        Args:
            company_id: Tenant company identifier.

        Returns:
            Number of records removed.
        """
        try:
            with self._lock:
                records = self._company_records.pop(
                    company_id, [],
                )
                self._collector.reset_metrics(
                    company_id=company_id,
                )
                return len(records)
        except Exception:
            return 0
