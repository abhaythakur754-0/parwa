"""
Technique Execution Metrics Collector (Week 10 Day 3)

Comprehensive metrics tracking for reasoning technique executions:
- Execution count, success/failure rate per technique
- Average execution time per technique
- Token usage tracking per technique
- Per-variant metrics breakdown (mini_parwa, parwa, parwa_high)
- Per-company metrics isolation
- Time-windowed metrics (last 1min, 5min, 15min, 1hr)
- Metrics aggregation (sum, avg, p50, p95, p99)
- Techniques leaderboard (most/least used, slowest, most tokens)
- Metrics reset/cleanup for stale entries

Thread-safe with threading.Lock.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
)


# ── Time Windows ───────────────────────────────────────────────────

TIME_WINDOWS_SECONDS = {
    "1min": 60,
    "5min": 300,
    "15min": 900,
    "1hr": 3600,
}

VALID_VARIANTS = ("mini_parwa", "parwa", "parwa_high")


# ── Data Structures ────────────────────────────────────────────────


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ExecutionRecord:
    """Single execution data point."""

    technique_id: str
    variant: str
    company_id: str
    status: ExecutionStatus
    tokens_used: int
    exec_time_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class TechniqueStats:
    """Aggregated statistics for a single technique."""

    technique_id: str
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    total_tokens: int = 0
    total_exec_time_ms: float = 0.0
    min_exec_time_ms: float = float("inf")
    max_exec_time_ms: float = 0.0
    exec_times: List[float] = field(default_factory=list)


@dataclass
class VariantSummary:
    """Aggregated summary for a single variant."""

    variant: str
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_tokens: int = 0
    total_exec_time_ms: float = 0.0
    technique_counts: Dict[str, int] = field(
        default_factory=dict,
    )


@dataclass
class LeaderboardEntry:
    """Single entry in a technique leaderboard."""

    technique_id: str
    value: float
    label: str = ""


# ── Metrics Collector ──────────────────────────────────────────────


class TechniqueMetricsCollector:
    """
    Thread-safe collector for technique execution metrics.

    Tracks execution counts, timing, token usage, and success rates
    per technique, variant, and company. Supports time-windowed queries,
    percentile calculations, and leaderboards.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Raw records: keyed by (technique_id, company_id)
        self._records: Dict[
            Tuple[str, str], List[ExecutionRecord]
        ] = defaultdict(list)

        # Aggregated stats: keyed by (technique_id, company_id)
        self._stats: Dict[
            Tuple[str, str], TechniqueStats
        ] = {}

        # Variant stats: keyed by variant
        self._variant_stats: Dict[str, VariantSummary] = {}

    # ── Recording ─────────────────────────────────────────────────

    def record_execution(
        self,
        technique_id: str,
        variant: str = "parwa",
        company_id: str = "default",
        status: str = "success",
        tokens_used: int = 0,
        exec_time_ms: float = 0.0,
    ) -> None:
        """
        Record a single technique execution.

        Args:
            technique_id: Technique identifier (e.g. 'clara')
            variant: Execution variant
                (mini_parwa, parwa, parwa_high)
            company_id: Tenant company identifier
            status: Execution status
                (success, failure, timeout, error)
            tokens_used: Number of tokens consumed
            exec_time_ms: Execution time in milliseconds
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        status_enum = ExecutionStatus(status)
        now = time.time()

        record = ExecutionRecord(
            technique_id=technique_id,
            variant=variant,
            company_id=company_id,
            status=status_enum,
            tokens_used=tokens_used,
            exec_time_ms=exec_time_ms,
            timestamp=now,
        )

        with self._lock:
            key = (technique_id, company_id)
            self._records[key].append(record)
            self._update_stats(key, record)
            self._update_variant_stats(record)

    def _update_stats(
        self, key: Tuple[str, str], record: ExecutionRecord,
    ) -> None:
        """Update aggregated stats for a technique/company pair."""
        if key not in self._stats:
            self._stats[key] = TechniqueStats(
                technique_id=key[0],
            )

        stats = self._stats[key]
        stats.total_executions += 1

        if record.status == ExecutionStatus.SUCCESS:
            stats.success_count += 1
        elif record.status == ExecutionStatus.FAILURE:
            stats.failure_count += 1
        elif record.status == ExecutionStatus.TIMEOUT:
            stats.timeout_count += 1
        else:
            stats.error_count += 1

        stats.total_tokens += record.tokens_used
        stats.total_exec_time_ms += record.exec_time_ms
        stats.exec_times.append(record.exec_time_ms)

        if record.exec_time_ms < stats.min_exec_time_ms:
            stats.min_exec_time_ms = record.exec_time_ms
        if record.exec_time_ms > stats.max_exec_time_ms:
            stats.max_exec_time_ms = record.exec_time_ms

    def _update_variant_stats(
        self, record: ExecutionRecord,
    ) -> None:
        """Update aggregated stats for a variant."""
        variant = record.variant
        if variant not in self._variant_stats:
            self._variant_stats[variant] = VariantSummary(
                variant=variant,
            )

        vs = self._variant_stats[variant]
        vs.total_executions += 1

        if record.status == ExecutionStatus.SUCCESS:
            vs.success_count += 1
        else:
            vs.failure_count += 1

        vs.total_tokens += record.tokens_used
        vs.total_exec_time_ms += record.exec_time_ms
        vs.technique_counts[record.technique_id] = (
            vs.technique_counts.get(record.technique_id, 0) + 1
        )

    # ── Query Methods ─────────────────────────────────────────────

    def get_technique_stats(
        self,
        technique_id: str,
        company_id: Optional[str] = None,
    ) -> Optional[TechniqueStats]:
        """
        Get aggregated stats for a technique.

        Args:
            technique_id: Technique identifier
            company_id: If None, aggregates across all companies

        Returns:
            TechniqueStats or None if no data exists
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        with self._lock:
            if company_id is not None:
                key = (technique_id, company_id)
                stats = self._stats.get(key)
                return self._copy_stats(stats) if stats else None

            # Aggregate across all companies
            all_stats: List[TechniqueStats] = []
            for (tid, cid), st in self._stats.items():
                if tid == technique_id:
                    all_stats.append(st)

            if not all_stats:
                return None

            return self._merge_stats(technique_id, all_stats)

    def get_variant_summary(
        self, variant: str,
    ) -> Optional[VariantSummary]:
        """Get aggregated summary for a variant."""
        with self._lock:
            vs = self._variant_stats.get(variant)
            if vs is None:
                return None
            return VariantSummary(
                variant=vs.variant,
                total_executions=vs.total_executions,
                success_count=vs.success_count,
                failure_count=vs.failure_count,
                total_tokens=vs.total_tokens,
                total_exec_time_ms=vs.total_exec_time_ms,
                technique_counts=dict(vs.technique_counts),
            )

    def get_all_variant_summaries(
        self,
    ) -> Dict[str, VariantSummary]:
        """Get summaries for all variants."""
        with self._lock:
            result = {}
            for v, vs in self._variant_stats.items():
                result[v] = VariantSummary(
                    variant=vs.variant,
                    total_executions=vs.total_executions,
                    success_count=vs.success_count,
                    failure_count=vs.failure_count,
                    total_tokens=vs.total_tokens,
                    total_exec_time_ms=vs.total_exec_time_ms,
                    technique_counts=dict(vs.technique_counts),
                )
            return result

    def get_time_windowed_stats(
        self,
        technique_id: str,
        window: str = "5min",
        company_id: Optional[str] = None,
    ) -> TechniqueStats:
        """
        Get stats for a technique within a time window.

        Args:
            technique_id: Technique identifier
            window: Time window key ('1min', '5min', '15min', '1hr')
            company_id: If None, aggregates across all companies

        Returns:
            TechniqueStats (possibly with zero counts)
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        window_seconds = TIME_WINDOWS_SECONDS.get(window, 300)
        cutoff = time.time() - window_seconds

        with self._lock:
            filtered_records: List[ExecutionRecord] = []
            for (tid, cid), records in self._records.items():
                if tid != technique_id:
                    continue
                if company_id is not None and cid != company_id:
                    continue
                for r in records:
                    if r.timestamp >= cutoff:
                        filtered_records.append(r)

            stats = TechniqueStats(technique_id=technique_id)
            for r in filtered_records:
                stats.total_executions += 1
                if r.status == ExecutionStatus.SUCCESS:
                    stats.success_count += 1
                elif r.status == ExecutionStatus.FAILURE:
                    stats.failure_count += 1
                elif r.status == ExecutionStatus.TIMEOUT:
                    stats.timeout_count += 1
                else:
                    stats.error_count += 1
                stats.total_tokens += r.tokens_used
                stats.total_exec_time_ms += r.exec_time_ms
                stats.exec_times.append(r.exec_time_ms)
                if r.exec_time_ms < stats.min_exec_time_ms:
                    stats.min_exec_time_ms = r.exec_time_ms
                if r.exec_time_ms > stats.max_exec_time_ms:
                    stats.max_exec_time_ms = r.exec_time_ms

            if not filtered_records:
                stats.min_exec_time_ms = 0.0
                stats.max_exec_time_ms = 0.0

            return stats

    # ── Percentiles ───────────────────────────────────────────────

    def get_percentiles(
        self,
        metric: str = "exec_time_ms",
        technique_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Calculate percentile statistics.

        Args:
            metric: 'exec_time_ms' or 'tokens_used'
            technique_id: Filter by technique (None = all)
            company_id: Filter by company (None = all)

        Returns:
            Dict with p50, p95, p99 keys
        """
        with self._lock:
            values: List[float] = []
            for (tid, cid), records in self._records.items():
                if technique_id is not None and tid != technique_id:
                    continue
                if company_id is not None and cid != company_id:
                    continue
                for r in records:
                    if metric == "exec_time_ms":
                        values.append(r.exec_time_ms)
                    elif metric == "tokens_used":
                        values.append(float(r.tokens_used))

            return self._calculate_percentiles(values)

    def get_company_percentiles(
        self,
        company_id: str,
        metric: str = "exec_time_ms",
    ) -> Dict[str, float]:
        """Get percentile stats for a specific company."""
        return self.get_percentiles(
            metric=metric,
            company_id=company_id,
        )

    @staticmethod
    def _calculate_percentiles(
        values: List[float],
    ) -> Dict[str, float]:
        """Calculate p50, p95, p99 from a list of values."""
        if not values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def percentile(p: float) -> float:
            idx = int(p / 100.0 * (n - 1))
            return round(sorted_vals[idx], 2)

        return {
            "p50": percentile(50),
            "p95": percentile(95),
            "p99": percentile(99),
        }

    # ── Leaderboard ───────────────────────────────────────────────

    def get_leaderboard(
        self,
        sort_by: str = "total_executions",
        limit: int = 10,
        company_id: Optional[str] = None,
    ) -> List[LeaderboardEntry]:
        """
        Get techniques leaderboard.

        Args:
            sort_by: Sorting metric
                ('total_executions', 'success_rate',
                 'avg_exec_time_ms', 'total_tokens',
                 'avg_tokens', 'failure_rate')
            limit: Maximum entries to return
            company_id: Filter by company (None = all)

        Returns:
            List of LeaderboardEntry sorted descending
        """
        valid_sort_keys = {
            "total_executions",
            "success_rate",
            "avg_exec_time_ms",
            "total_tokens",
            "avg_tokens",
            "failure_rate",
        }
        if sort_by not in valid_sort_keys:
            sort_by = "total_executions"

        with self._lock:
            technique_data: Dict[str, Dict[str, Any]] = {}

            for (tid, cid), stats in self._stats.items():
                if company_id is not None and cid != company_id:
                    continue

                if tid not in technique_data:
                    technique_data[tid] = {
                        "total_executions": 0,
                        "success_count": 0,
                        "failure_count": 0,
                        "total_tokens": 0,
                        "total_exec_time_ms": 0.0,
                        "exec_time_count": 0,
                    }

                td = technique_data[tid]
                td["total_executions"] += stats.total_executions
                td["success_count"] += stats.success_count
                td["failure_count"] += (
                    stats.failure_count
                    + stats.timeout_count
                    + stats.error_count
                )
                td["total_tokens"] += stats.total_tokens
                td["total_exec_time_ms"] += (
                    stats.total_exec_time_ms
                )
                td["exec_time_count"] += len(stats.exec_times)

            entries: List[LeaderboardEntry] = []
            for tid, td in technique_data.items():
                total = td["total_executions"]
                if total == 0:
                    continue

                if sort_by == "total_executions":
                    value = float(total)
                elif sort_by == "success_rate":
                    value = (
                        td["success_count"] / total * 100.0
                    )
                elif sort_by == "failure_rate":
                    value = (
                        td["failure_count"] / total * 100.0
                    )
                elif sort_by == "avg_exec_time_ms":
                    count = td["exec_time_count"] or 1
                    value = (
                        td["total_exec_time_ms"] / count
                    )
                elif sort_by == "total_tokens":
                    value = float(td["total_tokens"])
                elif sort_by == "avg_tokens":
                    value = td["total_tokens"] / total
                else:
                    value = float(total)

                entries.append(LeaderboardEntry(
                    technique_id=tid,
                    value=round(value, 2),
                    label=sort_by,
                ))

            entries.sort(key=lambda e: e.value, reverse=True)
            return entries[:limit]

    # ── Reset / Cleanup ───────────────────────────────────────────

    def reset_metrics(
        self, company_id: Optional[str] = None,
    ) -> int:
        """
        Reset metrics.

        Args:
            company_id: If None, reset all. If specified,
                reset only that company's metrics.

        Returns:
            Number of technique entries reset
        """
        with self._lock:
            if company_id is None:
                count = len(self._stats)
                self._records.clear()
                self._stats.clear()
                self._variant_stats.clear()
                return count

            keys_to_remove = [
                (tid, cid)
                for tid, cid in self._records
                if cid == company_id
            ]
            for key in keys_to_remove:
                del self._records[key]
                self._stats.pop(key, None)

            # Recalculate variant stats
            self._recalculate_variant_stats()
            return len(keys_to_remove)

    def cleanup_stale(self, max_age_seconds: float = 3600) -> int:
        """
        Remove records older than max_age_seconds.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of records removed
        """
        cutoff = time.time() - max_age_seconds

        with self._lock:
            removed = 0

            for key in list(self._records.keys()):
                tid, cid = key
                before = len(self._records[key])
                self._records[key] = [
                    r for r in self._records[key]
                    if r.timestamp >= cutoff
                ]
                removed += before - len(self._records[key])

                # Remove empty keys
                if not self._records[key]:
                    del self._records[key]
                    self._stats.pop(key, None)

            # Recalculate all stats
            self._stats.clear()
            self._variant_stats.clear()
            for key, records in self._records.items():
                for r in records:
                    self._update_stats(key, r)
                    self._update_variant_stats(r)

            return removed

    def _recalculate_variant_stats(self) -> None:
        """Recalculate variant stats from remaining records."""
        self._variant_stats.clear()
        for key, records in self._records.items():
            for r in records:
                self._update_variant_stats(r)

    # ── Internal Helpers ──────────────────────────────────────────

    @staticmethod
    def _copy_stats(
        stats: Optional[TechniqueStats],
    ) -> Optional[TechniqueStats]:
        """Create a copy of TechniqueStats."""
        if stats is None:
            return None
        return TechniqueStats(
            technique_id=stats.technique_id,
            total_executions=stats.total_executions,
            success_count=stats.success_count,
            failure_count=stats.failure_count,
            timeout_count=stats.timeout_count,
            error_count=stats.error_count,
            total_tokens=stats.total_tokens,
            total_exec_time_ms=stats.total_exec_time_ms,
            min_exec_time_ms=stats.min_exec_time_ms,
            max_exec_time_ms=stats.max_exec_time_ms,
            exec_times=list(stats.exec_times),
        )

    @staticmethod
    def _merge_stats(
        technique_id: str,
        stats_list: List[TechniqueStats],
    ) -> TechniqueStats:
        """Merge multiple TechniqueStats into one."""
        merged = TechniqueStats(technique_id=technique_id)
        for s in stats_list:
            merged.total_executions += s.total_executions
            merged.success_count += s.success_count
            merged.failure_count += s.failure_count
            merged.timeout_count += s.timeout_count
            merged.error_count += s.error_count
            merged.total_tokens += s.total_tokens
            merged.total_exec_time_ms += s.total_exec_time_ms
            merged.exec_times.extend(s.exec_times)
            if s.min_exec_time_ms < merged.min_exec_time_ms:
                merged.min_exec_time_ms = s.min_exec_time_ms
            if s.max_exec_time_ms > merged.max_exec_time_ms:
                merged.max_exec_time_ms = s.max_exec_time_ms
        return merged

    def get_record_count(self) -> int:
        """Get total number of records across all techniques."""
        with self._lock:
            return sum(len(r) for r in self._records.values())

    def get_technique_count(self) -> int:
        """Get number of unique technique+company pairs."""
        with self._lock:
            return len(self._stats)

    def get_company_ids(self) -> List[str]:
        """Get all unique company IDs."""
        with self._lock:
            ids = {cid for _, cid in self._records}
            return sorted(ids)
