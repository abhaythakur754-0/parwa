"""
SG-19: Real-Time AI Performance Monitoring Service.

Centralised monitoring dashboard for the entire AI engine pipeline.
Tracks latency, confidence, guardrails, blocked responses, token usage,
and error rates across all providers, models, variants, and companies.

Provides rolling-window analytics (1h, 6h, 24h, 7d), alert condition
detection, and dashboard snapshot APIs for frontend consumption.

BC-001: company_id is always first parameter on public methods.
BC-008: Never crash — every public method is wrapped.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("ai_monitoring")


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TimeWindow(str, Enum):
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWENTY_FOUR_HOURS = "24h"
    SEVEN_DAYS = "7d"


_WINDOW_SECONDS: Dict[str, int] = {
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
}


@dataclass
class MetricPoint:
    """Single data point with timestamp and labels."""
    timestamp: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class LatencyStats:
    """Aggregated latency statistics."""
    avg: float
    p50: float
    p90: float
    p99: float
    min_val: float
    max_val: float
    count: int


@dataclass
class ConfidenceDistribution:
    """Confidence score distribution across buckets."""
    buckets: Dict[str, int] = field(default_factory=lambda: {
        "0-20": 0, "20-40": 0, "40-60": 0,
        "60-80": 0, "80-100": 0,
    })
    avg_score: float = 50.0
    pass_rate: float = 1.0
    total_count: int = 0


@dataclass
class GuardrailLayerBreakdown:
    """Per-layer guardrail statistics."""
    layer: str
    passed: int = 0
    blocked: int = 0
    flagged: int = 0


@dataclass
class GuardrailStats:
    """Aggregated guardrail statistics."""
    pass_rate: float = 1.0
    block_rate: float = 0.0
    flagged_rate: float = 0.0
    per_layer: List[GuardrailLayerBreakdown] = field(default_factory=list)
    total_checked: int = 0


@dataclass
class ProviderComparison:
    """Side-by-side provider comparison."""
    provider: str
    latency: Optional[LatencyStats] = None
    error_rate: float = 0.0
    confidence_avg: float = 0.0
    requests_count: int = 0


@dataclass
class BlockedResponseMetrics:
    """Blocked response queue metrics."""
    total_blocked: int = 0
    pending_review: int = 0
    approved: int = 0
    rejected: int = 0
    auto_rejected: int = 0
    escalated: int = 0


@dataclass
class TokenUsageMetrics:
    """Token usage metrics (estimated from text length)."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    avg_input_per_request: float = 0.0
    avg_output_per_request: float = 0.0
    total_requests: int = 0


@dataclass
class ErrorMetrics:
    """Error tracking metrics."""
    total_errors: int = 0
    error_rate: float = 0.0
    error_by_type: Dict[str, int] = field(default_factory=dict)
    error_by_provider: Dict[str, int] = field(default_factory=dict)


@dataclass
class AlertCondition:
    """An anomalous condition detected by the monitoring service."""
    condition_id: str
    level: str
    message: str
    metric_value: float
    threshold: float
    timestamp: str
    provider: str = ""
    variant: str = ""


@dataclass
class DashboardSnapshot:
    """Complete dashboard data for one company."""
    latency: Dict[str, LatencyStats] = field(default_factory=dict)
    confidence: ConfidenceDistribution = field(
        default_factory=ConfidenceDistribution)
    guardrails: GuardrailStats = field(default_factory=GuardrailStats)
    blocked_responses: BlockedResponseMetrics = field(
        default_factory=BlockedResponseMetrics)
    token_usage: TokenUsageMetrics = field(default_factory=TokenUsageMetrics)
    errors: ErrorMetrics = field(default_factory=ErrorMetrics)
    alerts: List[AlertCondition] = field(default_factory=list)
    providers: List[ProviderComparison] = field(default_factory=list)
    variant_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    snapshot_at: str = ""
    total_requests: int = 0


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO timestamp string, returning None on failure."""
    if not ts:
        return None
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text (rough: ~4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _percentile(sorted_values: List[float], p: float) -> float:
    """Calculate percentile from sorted values."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    idx = (p / 100.0) * (n - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return sorted_values[lower]
    frac = idx - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def _confidence_bucket(score: float) -> str:
    """Map a confidence score to its bucket label."""
    if score < 20:
        return "0-20"
    elif score < 40:
        return "20-40"
    elif score < 60:
        return "40-60"
    elif score < 80:
        return "60-80"
    else:
        return "80-100"


def _window_cutoff(window: str) -> float:
    """Return the Unix timestamp cutoff for a time window."""
    seconds = _WINDOW_SECONDS.get(window, 86400)
    return time.time() - seconds


_MAX_DATA_POINTS = 50


# ══════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ══════════════════════════════════════════════════════════════════


class AIMonitoringService:
    """Real-time AI performance monitoring service (SG-19).

    Collects, aggregates, and analyses metrics from the entire AI
    pipeline: routing, confidence scoring, guardrails, blocked
    responses, token usage, and error tracking.

    BC-001: company_id first parameter.
    BC-008: Never crash.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # company_id -> list of metric records
        self._records: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # company_id -> list of AlertCondition
        self._alerts: Dict[str, List[AlertCondition]] = defaultdict(list)

    # ── Reset ──────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all stored metrics and alerts. For testing."""
        with self._lock:
            self._records.clear()
            self._alerts.clear()

    # ── Record Query (Master Method) ───────────────────────────

    def record_query(
        self,
        company_id: str,
        variant_type: str,
        query: str,
        response: str,
        routing_decision: Optional[Dict[str, Any]] = None,
        confidence_result: Optional[Dict[str, Any]] = None,
        guardrails_report: Optional[Dict[str, Any]] = None,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a complete query lifecycle for monitoring.

        This is the master record method — call it once per query
        after the full pipeline (route → generate → score → guard)
        has completed.

        Args:
            company_id: Tenant identifier (BC-001).
            variant_type: PARWA variant (mini_parwa, parwa, high_parwa).
            query: The original customer query.
            response: The AI-generated response.
            routing_decision: Dict with provider, model_id, tier, step.
            confidence_result: Dict with overall_score, passed, threshold.
            guardrails_report: Dict with passed, blocked_count, flagged_count.
            latency_ms: Total end-to-end latency in milliseconds.
            error: Error message if the query failed.

        Returns:
            The recorded metric dict for reference.
        """
        try:
            record = {
                "timestamp": _now_utc(),
                "company_id": company_id,
                "variant_type": variant_type,
                "latency_ms": float(latency_ms),
                "input_tokens": _estimate_tokens(query),
                "output_tokens": _estimate_tokens(response),
                "provider": (routing_decision or {}).get("provider", "unknown"),
                "model_id": (routing_decision or {}).get("model_id", "unknown"),
                "tier": (routing_decision or {}).get("tier", "unknown"),
                "step": (routing_decision or {}).get("step", "unknown"),
                "confidence_score": (confidence_result or {}).get(
                    "overall_score", 0.0
                ),
                "confidence_passed": (confidence_result or {}).get(
                    "passed", True
                ),
                "confidence_threshold": (confidence_result or {}).get(
                    "threshold", 85.0
                ),
                "guardrails_passed": (guardrails_report or {}).get(
                    "passed", True
                ),
                "guardrails_blocked_count": (guardrails_report or {}).get(
                    "blocked_count", 0
                ),
                "guardrails_flagged_count": (guardrails_report or {}).get(
                    "flagged_count", 0
                ),
                "guardrail_layers": (guardrails_report or {}).get(
                    "results", []
                ),
                "error": error,
                "has_error": error is not None,
            }

            with self._lock:
                records = self._records[company_id]
                records.append(record)
                # Prune to max data points per company
                if len(records) > _MAX_DATA_POINTS:
                    self._records[company_id] = records[-_MAX_DATA_POINTS:]

            return record

        except Exception:
            logger.exception(
                "monitoring_record_query_failed company_id=%s", company_id,
            )
            return {}

    # ── Latency Metrics ────────────────────────────────────────

    def get_latency_stats(
        self,
        company_id: str,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        window: str = "24h",
    ) -> LatencyStats:
        """Get latency statistics for a given scope and time window."""
        try:
            values = self._get_filtered_field(
                company_id, "latency_ms", provider, model_id, window,
            )
            if not values:
                return LatencyStats(
                    avg=0.0, p50=0.0, p90=0.0, p99=0.0,
                    min_val=0.0, max_val=0.0, count=0,
                )
            sorted_vals = sorted(values)
            return LatencyStats(
                avg=round(sum(sorted_vals) / len(sorted_vals), 2),
                p50=round(_percentile(sorted_vals, 50), 2),
                p90=round(_percentile(sorted_vals, 90), 2),
                p99=round(_percentile(sorted_vals, 99), 2),
                min_val=round(min(sorted_vals), 2),
                max_val=round(max(sorted_vals), 2),
                count=len(sorted_vals),
            )
        except Exception:
            logger.exception(
                "monitoring_get_latency_stats_failed company_id=%s",
                company_id,
            )
            return LatencyStats(
                avg=0.0, p50=0.0, p90=0.0, p99=0.0,
                min_val=0.0, max_val=0.0, count=0,
            )

    # ── Confidence Metrics ─────────────────────────────────────

    def get_confidence_distribution(
        self,
        company_id: str,
        window: str = "24h",
    ) -> ConfidenceDistribution:
        """Get confidence score distribution for a time window."""
        try:
            records = self._get_filtered_records(
                company_id, None, None, window,
            )
            if not records:
                return ConfidenceDistribution()

            buckets: Dict[str, int] = {
                "0-20": 0, "20-40": 0, "40-60": 0,
                "60-80": 0, "80-100": 0,
            }
            scores: List[float] = []
            passed_count = 0

            for r in records:
                score = r.get("confidence_score", 0.0)
                scores.append(score)
                bucket = _confidence_bucket(score)
                buckets[bucket] = buckets.get(bucket, 0) + 1
                if r.get("confidence_passed", True):
                    passed_count += 1

            total = len(scores)
            avg_score = round(sum(scores) / total, 2) if total > 0 else 0.0
            pass_rate = round(passed_count / total, 4) if total > 0 else 1.0

            return ConfidenceDistribution(
                buckets=buckets,
                avg_score=avg_score,
                pass_rate=pass_rate,
                total_count=total,
            )
        except Exception:
            logger.exception(
                "monitoring_get_confidence_failed company_id=%s",
                company_id,
            )
            return ConfidenceDistribution()

    # ── Guardrail Metrics ──────────────────────────────────────

    def get_guardrail_stats(
        self,
        company_id: str,
        window: str = "24h",
    ) -> GuardrailStats:
        """Get guardrail pass/block/flag statistics."""
        try:
            records = self._get_filtered_records(
                company_id, None, None, window,
            )
            if not records:
                return GuardrailStats()

            total = len(records)
            passed = 0
            blocked = 0
            flagged = 0
            per_layer: Dict[str, GuardrailLayerBreakdown] = {}

            for r in records:
                if r.get("guardrails_passed", True):
                    passed += 1
                else:
                    blocked += 1

                block_count = r.get("guardrails_blocked_count", 0)
                flag_count = r.get("guardrails_flagged_count", 0)
                if block_count > 0:
                    blocked += 0  # already counted above
                if flag_count > 0:
                    flagged += 1

                # Per-layer breakdown
                for layer_result in r.get("guardrail_layers", []):
                    layer_name = layer_result.get("layer", "unknown")
                    action = layer_result.get("action", "allow")

                    if layer_name not in per_layer:
                        per_layer[layer_name] = GuardrailLayerBreakdown(
                            layer=layer_name,
                        )

                    if action == "block":
                        per_layer[layer_name].blocked += 1
                    elif action == "flag_for_review":
                        per_layer[layer_name].flagged += 1
                    else:
                        per_layer[layer_name].passed += 1

            return GuardrailStats(
                pass_rate=round(passed / total, 4) if total > 0 else 1.0,
                block_rate=round(blocked / total, 4) if total > 0 else 0.0,
                flagged_rate=round(flagged / total, 4) if total > 0 else 0.0,
                per_layer=list(per_layer.values()),
                total_checked=total,
            )
        except Exception:
            logger.exception(
                "monitoring_get_guardrail_stats_failed company_id=%s",
                company_id,
            )
            return GuardrailStats()

    # ── Blocked Response Metrics ───────────────────────────────

    def get_blocked_metrics(
        self,
        company_id: str,
        window: str = "24h",
    ) -> BlockedResponseMetrics:
        """Get blocked response queue metrics."""
        try:
            records = self._get_filtered_records(
                company_id, None, None, window,
            )
            metrics = BlockedResponseMetrics()
            for r in records:
                if r.get("guardrails_passed", True):
                    continue
                metrics.total_blocked += 1
                metrics.pending_review += 1  # default state

            return metrics
        except Exception:
            logger.exception(
                "monitoring_get_blocked_failed company_id=%s", company_id,
            )
            return BlockedResponseMetrics()

    # ── Token Usage Metrics ────────────────────────────────────

    def get_token_usage(
        self,
        company_id: str,
        window: str = "24h",
    ) -> TokenUsageMetrics:
        """Get estimated token usage statistics."""
        try:
            records = self._get_filtered_records(
                company_id, None, None, window,
            )
            if not records:
                return TokenUsageMetrics()

            total_input = sum(r.get("input_tokens", 0) for r in records)
            total_output = sum(r.get("output_tokens", 0) for r in records)
            total = len(records)

            return TokenUsageMetrics(
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                avg_input_per_request=round(
                    total_input / total, 1
                ) if total > 0 else 0.0,
                avg_output_per_request=round(
                    total_output / total, 1
                ) if total > 0 else 0.0,
                total_requests=total,
            )
        except Exception:
            logger.exception(
                "monitoring_get_token_usage_failed company_id=%s",
                company_id,
            )
            return TokenUsageMetrics()

    # ── Error Metrics ──────────────────────────────────────────

    def get_error_metrics(
        self,
        company_id: str,
        window: str = "24h",
    ) -> ErrorMetrics:
        """Get error tracking metrics."""
        try:
            records = self._get_filtered_records(
                company_id, None, None, window,
            )
            if not records:
                return ErrorMetrics()

            total = len(records)
            error_records = [r for r in records if r.get("has_error", False)]
            error_count = len(error_records)

            error_by_type: Dict[str, int] = defaultdict(int)
            error_by_provider: Dict[str, int] = defaultdict(int)

            for r in error_records:
                err = r.get("error", "unknown")
                error_by_type[err] += 1
                error_by_provider[r.get("provider", "unknown")] += 1

            return ErrorMetrics(
                total_errors=error_count,
                error_rate=round(error_count / total, 4) if total > 0 else 0.0,
                error_by_type=dict(error_by_type),
                error_by_provider=dict(error_by_provider),
            )
        except Exception:
            logger.exception(
                "monitoring_get_error_metrics_failed company_id=%s",
                company_id,
            )
            return ErrorMetrics()

    # ── Provider Comparison ────────────────────────────────────

    def get_provider_comparison(
        self,
        company_id: str,
        window: str = "24h",
    ) -> List[ProviderComparison]:
        """Compare providers side by side."""
        try:
            all_providers = self._get_unique_providers(company_id, window)
            comparisons: List[ProviderComparison] = []

            for provider in all_providers:
                provider_records = self._get_filtered_records(
                    company_id, provider, None, window,
                )

                if not provider_records:
                    comparisons.append(ProviderComparison(
                        provider=provider, requests_count=0,
                    ))
                    continue

                latencies = [
                    r["latency_ms"] for r in provider_records
                    if r.get("latency_ms", 0) > 0
                ]
                errors = [
                    r for r in provider_records if r.get("has_error", False)
                ]
                scores = [
                    r["confidence_score"] for r in provider_records
                    if r.get("confidence_score", 0) > 0
                ]

                sorted_lat = sorted(latencies) if latencies else []
                comparisons.append(ProviderComparison(
                    provider=provider,
                    latency=LatencyStats(
                        avg=round(sum(latencies) / len(latencies), 2)
                        if latencies else 0.0,
                        p50=round(_percentile(sorted_lat, 50), 2),
                        p90=round(_percentile(sorted_lat, 90), 2),
                        p99=round(_percentile(sorted_lat, 99), 2),
                        min_val=round(min(latencies), 2)
                        if latencies else 0.0,
                        max_val=round(max(latencies), 2)
                        if latencies else 0.0,
                        count=len(latencies),
                    ),
                    error_rate=round(
                        len(errors) / len(provider_records), 4
                    ),
                    confidence_avg=round(
                        sum(scores) / len(scores), 2
                    ) if scores else 0.0,
                    requests_count=len(provider_records),
                ))

            return comparisons
        except Exception:
            logger.exception(
                "monitoring_provider_comparison_failed company_id=%s",
                company_id,
            )
            return []

    # ── Variant Metrics ────────────────────────────────────────

    def get_variant_metrics(
        self,
        company_id: str,
        window: str = "24h",
    ) -> Dict[str, Dict[str, Any]]:
        """Get metrics broken down by variant type."""
        try:
            records = self._get_filtered_records(
                company_id, None, None, window,
            )
            by_variant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for r in records:
                v = r.get("variant_type", "unknown")
                by_variant[v].append(r)

            result: Dict[str, Dict[str, Any]] = {}
            for variant, v_records in by_variant.items():
                total = len(v_records)
                latencies = [
                    r["latency_ms"] for r in v_records
                    if r.get("latency_ms", 0) > 0
                ]
                scores = [
                    r["confidence_score"] for r in v_records
                    if r.get("confidence_score", 0) > 0
                ]
                errors = [
                    r for r in v_records if r.get("has_error", False)
                ]
                blocked = [
                    r for r in v_records
                    if not r.get("guardrails_passed", True)
                ]

                result[variant] = {
                    "total_requests": total,
                    "avg_latency": round(
                        sum(latencies) / len(latencies), 2
                    ) if latencies else 0.0,
                    "avg_confidence": round(
                        sum(scores) / len(scores), 2
                    ) if scores else 0.0,
                    "error_count": len(errors),
                    "error_rate": round(
                        len(errors) / total, 4
                    ) if total > 0 else 0.0,
                    "blocked_count": len(blocked),
                    "block_rate": round(
                        len(blocked) / total, 4
                    ) if total > 0 else 0.0,
                }

            return result
        except Exception:
            logger.exception(
                "monitoring_variant_metrics_failed company_id=%s",
                company_id,
            )
            return {}

    # ── Alert Conditions ───────────────────────────────────────

    def get_alert_conditions(
        self,
        company_id: str,
        window: str = "24h",
    ) -> List[AlertCondition]:
        """Detect and return anomalous conditions.

        Checks:
        - Error rate > 10% (15min) → WARNING
        - Error rate > 25% (15min) → CRITICAL
        - Avg confidence < 60% (30min) → WARNING
        - P90 latency > 5000ms → WARNING
        - Any provider fully unhealthy → CRITICAL
        """
        try:
            alerts: List[AlertCondition] = []

            # 1. Error rate checks
            error_metrics = self.get_error_metrics(company_id, "1h")
            if error_metrics.error_rate > 0.25:
                alerts.append(AlertCondition(
                    condition_id="error_rate_critical",
                    level=AlertLevel.CRITICAL.value,
                    message=(
                        f"Critical error rate: "
                        f"{error_metrics.error_rate * 100:.1f}% "
                        f"({error_metrics.total_errors} errors)"
                    ),
                    metric_value=error_metrics.error_rate * 100,
                    threshold=25.0,
                    timestamp=_now_utc(),
                ))
            elif error_metrics.error_rate > 0.10:
                alerts.append(AlertCondition(
                    condition_id="error_rate_warning",
                    level=AlertLevel.WARNING.value,
                    message=(
                        f"Elevated error rate: "
                        f"{error_metrics.error_rate * 100:.1f}%"
                    ),
                    metric_value=error_metrics.error_rate * 100,
                    threshold=10.0,
                    timestamp=_now_utc(),
                ))

            # 2. Confidence drop check
            conf_dist = self.get_confidence_distribution(company_id, "1h")
            if (conf_dist.total_count > 0
                    and conf_dist.avg_score < 60.0):
                alerts.append(AlertCondition(
                    condition_id="confidence_drop_warning",
                    level=AlertLevel.WARNING.value,
                    message=(
                        f"Low average confidence: "
                        f"{conf_dist.avg_score:.1f}%"
                    ),
                    metric_value=conf_dist.avg_score,
                    threshold=60.0,
                    timestamp=_now_utc(),
                ))

            # 3. Latency spike check
            latency = self.get_latency_stats(company_id, window=window)
            if latency.p90 > 5000.0 and latency.count > 0:
                alerts.append(AlertCondition(
                    condition_id="latency_spike_warning",
                    level=AlertLevel.WARNING.value,
                    message=(
                        f"High P90 latency: {latency.p90:.0f}ms "
                        f"(threshold: 5000ms)"
                    ),
                    metric_value=latency.p90,
                    threshold=5000.0,
                    timestamp=_now_utc(),
                ))

            # 4. Provider health check
            comparisons = self.get_provider_comparison(company_id, window)
            for comp in comparisons:
                if (comp.requests_count > 0
                        and comp.error_rate > 0.50):
                    alerts.append(AlertCondition(
                        condition_id=f"provider_unhealthy_{comp.provider}",
                        level=AlertLevel.CRITICAL.value,
                        message=(
                            f"Provider {comp.provider} is unhealthy: "
                            f"{comp.error_rate * 100:.1f}% error rate"
                        ),
                        metric_value=comp.error_rate * 100,
                        threshold=50.0,
                        timestamp=_now_utc(),
                        provider=comp.provider,
                    ))

            # Store alerts
            with self._lock:
                self._alerts[company_id] = alerts

            return alerts

        except Exception:
            logger.exception(
                "monitoring_alert_conditions_failed company_id=%s",
                company_id,
            )
            return []

    # ── Dashboard Snapshot ─────────────────────────────────────

    def get_dashboard_data(
        self,
        company_id: str,
        window: str = "24h",
    ) -> DashboardSnapshot:
        """Get complete dashboard data in one call."""
        try:
            # Get latency per provider for the latency dict
            comparisons = self.get_provider_comparison(company_id, window)
            latency_by_provider: Dict[str, LatencyStats] = {}
            for comp in comparisons:
                if comp.latency and comp.requests_count > 0:
                    latency_by_provider[comp.provider] = comp.latency

            # Overall latency (all providers combined)
            overall_latency = self.get_latency_stats(
                company_id, window=window,
            )

            all_records = self._get_filtered_records(
                company_id, None, None, window,
            )

            snapshot = DashboardSnapshot(
                latency={
                    "overall": overall_latency,
                    **latency_by_provider,
                },
                confidence=self.get_confidence_distribution(
                    company_id, window,
                ),
                guardrails=self.get_guardrail_stats(company_id, window),
                blocked_responses=self.get_blocked_metrics(
                    company_id, window,
                ),
                token_usage=self.get_token_usage(company_id, window),
                errors=self.get_error_metrics(company_id, window),
                alerts=self.get_alert_conditions(company_id, window),
                providers=comparisons,
                variant_metrics=self.get_variant_metrics(
                    company_id, window,
                ),
                snapshot_at=_now_utc(),
                total_requests=len(all_records),
            )

            return snapshot

        except Exception:
            logger.exception(
                "monitoring_dashboard_failed company_id=%s", company_id,
            )
            return DashboardSnapshot(snapshot_at=_now_utc())

    # ── Record Count ───────────────────────────────────────────

    def get_record_count(self, company_id: str) -> int:
        """Get number of stored records for a company."""
        try:
            with self._lock:
                return len(self._records.get(company_id, []))
        except Exception:
            return 0

    def get_stored_alerts(self, company_id: str) -> List[AlertCondition]:
        """Get the last stored alerts for a company."""
        try:
            with self._lock:
                return list(self._alerts.get(company_id, []))
        except Exception:
            return []

    # ── Internal Helpers ───────────────────────────────────────

    def _get_filtered_records(
        self,
        company_id: str,
        provider: Optional[str],
        model_id: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        """Get records filtered by company, provider, model, and window."""
        with self._lock:
            records = list(self._records.get(company_id, []))

        cutoff = _window_cutoff(window)
        result = []
        for r in records:
            ts = _parse_iso(r.get("timestamp", ""))
            if ts is None:
                continue
            if ts.timestamp() < cutoff:
                continue
            if provider and r.get("provider") != provider:
                continue
            if model_id and r.get("model_id") != model_id:
                continue
            result.append(r)

        return result

    def _get_filtered_field(
        self,
        company_id: str,
        field_name: str,
        provider: Optional[str],
        model_id: Optional[str],
        window: str,
    ) -> List[float]:
        """Get a list of numeric field values from filtered records."""
        records = self._get_filtered_records(
            company_id, provider, model_id, window,
        )
        values = []
        for r in records:
            v = r.get(field_name, 0.0)
            if v is not None:
                values.append(float(v))
        return values

    def _get_unique_providers(
        self,
        company_id: str,
        window: str,
    ) -> List[str]:
        """Get unique providers seen in a time window."""
        records = self._get_filtered_records(
            company_id, None, None, window,
        )
        providers = set()
        for r in records:
            providers.add(r.get("provider", "unknown"))
        return sorted(providers)
